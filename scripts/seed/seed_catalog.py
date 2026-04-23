import sys
import os
from pathlib import Path
import re
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

# Проверяем аргументы командной строки до импортов бэкенда
if "--sqlite" in sys.argv:
    os.environ["USE_SQLITE"] = "True"
    os.environ["USE_REDIS"] = "False"

from backend.db.session import async_session_factory, engine
from backend.models.sticker import StickerCatalog, PriorityMarket
from backend.models.issuer import Issuer
from backend.models.base import Base

def parse_final_catalog():
    """Парсим FinalCatalog.md и возвращаем список стикеров."""
    catalog_path = Path(__file__).parent / "FinalCatalog.md"
    if not catalog_path.exists():
        logger.error(f"FinalCatalog.md not found at {catalog_path}")
        return []

    with open(catalog_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Разделяем по стикерам (###)
    sticker_blocks = re.split(r'\n### ', content)
    # Первый блок может содержать заголовок коллекции (##), пропустим его если он не содержит ###
    if sticker_blocks and not content.startswith('### '):
        header_part = sticker_blocks.pop(0)
        # Можно извлечь коллекцию из header_part если нужно, 
        # но по логике пользователя коллекция берется из имени стикера до тире.

    stickers = []
    for block in sticker_blocks:
        lines = block.split('\n')
        if not lines:
            continue
            
        full_title = lines[0].strip()
        
        # Логика пользователя: 1 до тире - имя коллекции, 2 - имя стикера
        if " - " in full_title:
            parts = full_title.split(" - ", 1)
            collection_name = parts[0].strip()
            sticker_name = parts[1].strip()
        else:
            collection_name = "Default"
            sticker_name = full_title

        sticker_data = {
            "name": sticker_name,
            "collection_name": collection_name,
            "collection_address": None,
            "max_pool_size": 100,
            "lottie_url": None,
            "image_url": None,
            "issuer_name": "Goodies", # По умолчанию
            "chance": 0.0
        }

        # Парсим остальные строки блока
        for line in lines[1:]:
            line = line.strip()
            if line.startswith("- Collection Address:"):
                sticker_data["collection_address"] = line.split(":", 1)[1].strip()
            elif line.startswith("- Max Pool:"):
                try:
                    sticker_data["max_pool_size"] = int(line.split(":", 1)[1].strip())
                except:
                    pass
            elif line.startswith("- Issusier:"):
                sticker_data["issuer_name"] = line.split(":", 1)[1].strip()
            elif line.startswith("- Chanse:"):
                try:
                    chance_str = line.split(":", 1)[1].strip().replace('%', '')
                    sticker_data["chance"] = float(chance_str) / 100.0
                except:
                    pass
            elif line.startswith("- [") or line.startswith("  - ["):
                url_match = re.search(r"\((https?://[^\)]+)\)", line)
                if url_match:
                    url = url_match.group(1)
                    if url.endswith(".json"):
                        sticker_data["lottie_url"] = url
                    elif url.endswith(".webp") or url.endswith(".png") or url.endswith(".jpg"):
                        sticker_data["image_url"] = url

        if sticker_data["name"] and sticker_data["image_url"]:
            stickers.append(sticker_data)

    return stickers

async def seed_catalog():
    logger.info("Starting catalog seed from FinalCatalog.md...")

    if "--sqlite" in sys.argv:
        logger.info("Initializing tables for SQLite...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    stickers_data = parse_final_catalog()
    logger.info(f"Found {len(stickers_data)} stickers to process")

    async with async_session_factory() as db:
        # Предварительно загрузим всех эмитентов для кэша
        stmt = select(Issuer)
        result = await db.execute(stmt)
        issuers = {i.name: i for i in result.scalars().all()}
        # Добавим маппинг по slug если имя не совпадает
        issuers_by_slug = {i.slug: i for i in issuers.values()}

        for s_data in stickers_data:
            # Ищем эмитента
            issuer_name = s_data["issuer_name"]
            issuer = issuers.get(issuer_name) or issuers_by_slug.get(issuer_name.lower().replace(" ", ""))
            
            # Специальный маппинг для Slon -> Elephant Store
            if not issuer and issuer_name.lower() == "slon":
                issuer = issuers_by_slug.get("elephantstore")
            
            if not issuer:
                logger.warning(f"Issuer '{issuer_name}' not found for sticker '{s_data['name']}'")
                continue

            # Логика выбора маркета: 
            # 1. Slon (elephantstore) -> GetGems
            # 2. StickerStore -> Laffka
            # 3. Остальные -> GetGems
            is_slon = (issuer.slug == "elephantstore" or "slon" in issuer.name.lower())
            is_sticker_store = (issuer.slug == "stickerstore" or issuer.name == "Sticker Store")
            
            if is_slon:
                priority_market = PriorityMarket.GETGEMS
            elif is_sticker_store:
                priority_market = PriorityMarket.LAFFKA
            else:
                priority_market = PriorityMarket.GETGEMS

            # Проверка на существование
            stmt = select(StickerCatalog).where(
                StickerCatalog.name == s_data["name"],
                StickerCatalog.issuer_id == issuer.id
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Обновляем если нужно
                existing.collection_name = s_data["collection_name"]
                existing.image_url = s_data["image_url"]
                existing.lottie_url = s_data["lottie_url"]
                existing.collection_address = s_data["collection_address"]
                existing.max_pool_size = s_data["max_pool_size"]
                existing.priority_market = priority_market
                existing.is_onchain = bool(s_data["collection_address"])
                logger.info(f"Updated sticker: {s_data['name']}")
                continue

            # Создаем новый
            logger.info(f"Adding new sticker: {s_data['name']}")
            new_sticker = StickerCatalog(
                issuer_id=issuer.id,
                name=s_data["name"],
                collection_name=s_data["collection_name"],
                image_url=s_data["image_url"],
                lottie_url=s_data["lottie_url"],
                collection_address=s_data["collection_address"],
                max_pool_size=s_data["max_pool_size"],
                priority_market=priority_market,
                is_onchain=bool(s_data["collection_address"])
            )
            db.add(new_sticker)

        await db.commit()
        logger.info("Catalog seed completed!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_catalog())
