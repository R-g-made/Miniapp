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
from backend.models.sticker import StickerCatalog, ThermosMapping
from backend.models.base import Base

def parse_collections_report():
    """Парсим collections_report.md и возвращаем данные для маппинга."""
    report_path = Path(__file__).parent / "collections_report.md"
    if not report_path.exists():
        logger.error(f"collections_report.md not found at {report_path}")
        return []

    with open(report_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    mappings = []
    # Пропускаем заголовки таблицы (первые 2-3 строки)
    for line in lines:
        if '|' not in line or 'Character Name' in line or ':---' in line:
            continue
            
        parts = [p.strip() for p in line.split('|')]
        # | empty | Character Name | Collection Name | Character ID | Collection ID | empty |
        # Индексы: 1: Name, 2: Coll Name, 3: Char ID, 4: Coll ID
        if len(parts) >= 5:
            try:
                mappings.append({
                    "character_name": parts[1],
                    "collection_name": parts[2],
                    "character_id": int(parts[3]),
                    "collection_id": int(parts[4])
                })
            except ValueError:
                continue
    
    return mappings

def normalize_name(name: str) -> str:
    """Нормализация имени для сравнения"""
    if not name: return ""
    # Удаляем спецсимволы, лишние пробелы, приводим к нижнему регистру
    name = re.sub(r'[^a-zA-Z0-9а-яА-Я\s]', '', name.lower())
    # Удаляем общие слова-шум
    noise = ["pack", "collection", "case", "sticker", "store"]
    for word in noise:
        name = name.replace(word, "")
    return " ".join(name.split())

async def seed_thermos_mapping():
    logger.info("Starting Thermos mapping seed from collections_report.md...")

    if "--sqlite" in sys.argv:
        logger.info("Initializing tables for SQLite...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    mapping_data = parse_collections_report()
    logger.info(f"Found {len(mapping_data)} mappings to process")

    async with async_session_factory() as db:
        # Предварительно загрузим весь каталог для гибкого поиска
        stmt = select(StickerCatalog)
        result = await db.execute(stmt)
        catalog_items = result.scalars().all()

        added_count = 0
        updated_count = 0
        skipped_count = 0

        for m_data in mapping_data:
            char_name = m_data["character_name"]
            coll_name = m_data["collection_name"]
            
            norm_char = normalize_name(char_name)
            norm_coll = normalize_name(coll_name)
            
            # 1. Гибкий поиск существующего стикера
            sticker = None
            for item in catalog_items:
                norm_item_name = normalize_name(item.name)
                norm_item_coll = normalize_name(item.collection_name or "")
                
                # Точное совпадение имени и коллекции
                if norm_item_name == norm_char and (not norm_item_coll or norm_item_coll == norm_coll):
                    sticker = item
                    break
                
            # 2. Если не нашли - просто пропускаем (как просил пользователь)
            if not sticker:
                skipped_count += 1
                continue

            # 3. Проверка/Создание маппинга
            stmt = select(ThermosMapping).where(ThermosMapping.catalog_id == sticker.id)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.thermos_character_id = m_data["character_id"]
                existing.thermos_collection_id = m_data["collection_id"]
                existing.thermos_character_name = char_name
                existing.thermos_collection_name = coll_name
                updated_count += 1
                continue

            logger.info(f"Adding new Thermos mapping for: {char_name}")
            new_mapping = ThermosMapping(
                catalog_id=sticker.id,
                thermos_character_id=m_data["character_id"],
                thermos_collection_id=m_data["collection_id"],
                thermos_character_name=char_name,
                thermos_collection_name=coll_name
            )
            db.add(new_mapping)
            added_count += 1

        await db.commit()
        logger.success(f"Thermos mapping seed completed: added {added_count}, updated {updated_count}, skipped {skipped_count} missing stickers.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_thermos_mapping())
