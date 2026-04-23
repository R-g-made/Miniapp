import sys
import os
import json
import re
from pathlib import Path
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

# Проверяем аргументы командной строки до импортов бэкенда
if "--sqlite" in sys.argv:
    os.environ["USE_SQLITE"] = "True"
    os.environ["USE_REDIS"] = "False"

from backend.db.session import async_session_factory, engine
from backend.models.case import Case
from backend.models.associations import CaseItem, CaseIssuer
from backend.models.sticker import StickerCatalog
from backend.models.issuer import Issuer
from backend.models.base import Base

def parse_cases_md():
    """Парсим Case.md и возвращаем список кейсов."""
    case_path = Path(__file__).parent / "Case.md"
    if not case_path.exists():
        logger.error(f"Case.md not found at {case_path}")
        return []

    with open(case_path, "r", encoding="utf-8") as f:
        content = f.read().strip()

    cases = []
    # Разделяем по двойному переносу строки или по 'name:'
    blocks = re.split(r'\n(?=name:)', content)
    
    for block in blocks:
        lines = block.strip().split('\n')
        case_data = {
            "name": None,
            "slug": None,
            "img_url": None,
            "styles": {},
            "is_chance_distribution": False
        }
        for line in lines:
            if ':' not in line: continue
            key, val = [p.strip() for p in line.split(':', 1)]
            if key == 'name': case_data['name'] = val
            elif key == 'slug': case_data['slug'] = val
            elif key == 'img_url': case_data['img_url'] = val
            elif key == 'Style':
                try:
                    case_data['styles'] = json.loads(val)
                except:
                    pass
            elif key == 'is_chance_distribution':
                case_data['is_chance_distribution'] = val.lower() == 'true'
        
        if case_data['slug']:
            cases.append(case_data)
    
    return cases

def parse_case_items():
    """Парсим FinalCatalog.md и возвращаем маппинг кейс -> [стикеры]."""
    catalog_path = Path(__file__).parent / "FinalCatalog.md"
    if not catalog_path.exists():
        logger.error(f"FinalCatalog.md not found at {catalog_path}")
        return {}

    with open(catalog_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Разделяем по кейсам (##). Обрабатываем начало файла тоже.
    if content.startswith('## '):
        case_blocks = re.split(r'\n## |^## ', content)
    else:
        case_blocks = re.split(r'\n## ', content)
    
    case_mapping = {}

    for block in case_blocks:
        if not block.strip(): continue
        lines = block.split('\n')
        
        # Первая строка - название кейса
        case_header = lines[0].strip()
        if not case_header: continue
        
        # Парсим стикеры внутри кейса (###)
        sticker_blocks = re.split(r'\n### |^### ', block)
        if len(sticker_blocks) <= 1: continue # Нет стикеров
        
        stickers = []
        for s_block in sticker_blocks[1:]:
            s_lines = s_block.split('\n')
            if not s_lines: continue
            
            full_title = s_lines[0].strip()
            # По логике: "Collection - Name"
            if " - " in full_title:
                sticker_name = full_title.split(" - ", 1)[1].strip()
            else:
                sticker_name = full_title
            
            chance = 0.0
            issuer_name = "Goodies"
            
            for s_line in s_lines:
                s_line = s_line.strip()
                if s_line.startswith("- Chanse:"):
                    try:
                        # Убираем % и лишние пробелы
                        chance_str = s_line.split(":", 1)[1].strip().replace('%', '')
                        chance = float(chance_str) / 100.0
                    except: 
                        logger.warning(f"Failed to parse chance from line: {s_line}")
                elif s_line.startswith("- Issusier:"):
                    issuer_name = s_line.split(":", 1)[1].strip()
            
            stickers.append({
                "name": sticker_name,
                "chance": chance,
                "issuer_name": issuer_name
            })
        
        case_mapping[case_header] = stickers
    
    return case_mapping

async def seed_case():
    logger.info("Starting case and items seed...")

    if "--sqlite" in sys.argv:
        logger.info("Initializing tables for SQLite...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    cases_data = parse_cases_md()
    case_items_mapping = parse_case_items()
    
    async with async_session_factory() as db:
        # Загружаем всех эмитентов
        stmt = select(Issuer)
        result = await db.execute(stmt)
        issuers_map = {i.name: i for i in result.scalars().all()}
        issuers_by_slug = {i.slug: i for i in issuers_map.values()}

        for c_data in cases_data:
            # Проверяем существование кейса
            stmt = select(Case).where(Case.slug == c_data["slug"])
            result = await db.execute(stmt)
            case = result.scalar_one_or_none()
            
            if not case:
                logger.info(f"Creating new case: {c_data['name']} ({c_data['slug']})")
                case = Case(
                    slug=c_data["slug"],
                    name=c_data["name"],
                    image_url=c_data["img_url"],
                    price_ton=0.1, # Значение по умолчанию, если не указано
                    price_stars=5.0,
                    is_active=True,
                    is_chance_distribution=c_data["is_chance_distribution"],
                    styles=c_data["styles"]
                )
                db.add(case)
                await db.flush()
            else:
                # Обновляем метаданные
                case.name = c_data["name"]
                case.image_url = c_data["img_url"]
                case.styles = c_data["styles"]
                case.is_chance_distribution = c_data["is_chance_distribution"]
                logger.info(f"Updated case metadata: {c_data['slug']}")

            # Ищем содержимое для этого кейса в mapping
            # Сопоставляем по slug или имени
            found_items = []
            case_name_clean = case.name.lower().strip()
            case_slug_clean = case.slug.lower().replace("_", " ").strip()
            
            for header, items in case_items_mapping.items():
                header_clean = header.lower().replace(" case", "").strip()
                
                # Более гибкое сопоставление
                # 1. Прямое вхождение имен
                if case_name_clean in header_clean or header_clean in case_name_clean:
                    found_items = items
                    break
                # 2. Прямое вхождение слага
                if case_slug_clean in header_clean or header_clean in case_slug_clean:
                    found_items = items
                    break
                # 3. Специальный случай: Dogs <-> DOGES
                if ("dog" in case_name_clean or "dog" in case_slug_clean) and "dog" in header_clean:
                    found_items = items
                    break
            
            if not found_items:
                logger.warning(f"No items found in FinalCatalog.md for case {case.slug}")
                continue

            # Очищаем старые связи CaseItem для этого кейса перед добавлением новых
            # (чтобы избежать дублей и учесть изменения в MD)
            await db.execute(delete(CaseItem).where(CaseItem.case_id == case.id))
            await db.execute(delete(CaseIssuer).where(CaseIssuer.case_id == case.id))

            # Добавляем новые связи
            added_issuers = set()
            for item in found_items:
                # Ищем эмитента для этого стикера
                issuer_name = item["issuer_name"]
                issuer = issuers_map.get(issuer_name) or issuers_by_slug.get(issuer_name.lower().replace(" ", ""))
                
                # Специальный маппинг для Slon -> Elephant Store
                if not issuer and issuer_name.lower() == "slon":
                    issuer = issuers_by_slug.get("elephantstore")

                if not issuer:
                    logger.warning(f"Issuer '{issuer_name}' not found for item '{item['name']}' in case {case.slug}")
                    continue

                # Ищем стикер в каталоге с учетом эмитента
                stmt = select(StickerCatalog).where(
                    StickerCatalog.name == item["name"],
                    StickerCatalog.issuer_id == issuer.id
                )
                result = await db.execute(stmt)
                sticker = result.scalar_one_or_none()
                
                if not sticker:
                    logger.warning(f"Sticker '{item['name']}' (Issuer: {issuer.name}) not found in catalog, skipping item for case {case.slug}")
                    continue
                
                # Добавляем CaseItem
                db.add(CaseItem(
                    case_id=case.id,
                    sticker_catalog_id=sticker.id,
                    chance=item["chance"]
                ))
                
                # Добавляем эмитента кейса если еще не добавлен
                if issuer.id not in added_issuers:
                    db.add(CaseIssuer(
                        case_id=case.id,
                        issuer_id=issuer.id,
                        is_main=(len(added_issuers) == 0) # Первый будет главным
                    ))
                    added_issuers.add(issuer.id)

        await db.commit()
        logger.info("Case and items seed completed successfully!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_case())
