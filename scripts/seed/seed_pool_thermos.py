import sys
import os
from pathlib import Path
from loguru import logger
from sqlalchemy import select

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

# Проверяем аргументы командной строки до импортов бэкенда
if "--sqlite" in sys.argv:
    os.environ["USE_SQLITE"] = "True"
    os.environ["USE_REDIS"] = "False"

import asyncio
from backend.db.session import async_session_factory, engine
from backend.models.sticker import StickerCatalog, UserSticker, ThermosMapping
from backend.models.base import Base
from backend.services.thermos_service import thermos_service

async def seed_pool_thermos():
    logger.info("Starting sticker pool seed from Thermos API...")

    if "--sqlite" in sys.argv:
        logger.info("Initializing tables for SQLite...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # 1. Получаем список стикеров из Thermos
    thermos_stickers = await thermos_service.get_my_stickers()
    if not thermos_stickers:
        logger.warning("No stickers found in Thermos account.")
        return

    logger.info(f"Found {len(thermos_stickers)} stickers in Thermos")

    async with async_session_factory() as db:
        # 2. Загружаем все маппинги и каталог для кэша
        stmt = select(ThermosMapping)
        result = await db.execute(stmt)
        mappings = result.scalars().all()
        
        # Создаем маппинг (coll_id, char_id) -> catalog_id
        mapping_dict = {
            (m.thermos_collection_id, m.thermos_character_id): m.catalog_id 
            for m in mappings
        }
        
        # Загружаем каталог для получения цен
        stmt = select(StickerCatalog)
        result = await db.execute(stmt)
        catalog_items = {c.id: c for c in result.scalars().all()}

        added_count = 0
        skipped_count = 0

        for ts in thermos_stickers:
            coll_id = ts.get("collection_id")
            char_id = ts.get("character_id")
            instance = ts.get("instance")
            
            if coll_id is None or char_id is None or instance is None:
                continue
                
            catalog_id = mapping_dict.get((coll_id, char_id))
            if not catalog_id:
                # logger.debug(f"No mapping found for Thermos sticker {coll_id}:{char_id}")
                continue
                
            catalog = catalog_items.get(catalog_id)
            if not catalog:
                continue

            # 3. Проверяем на дубликаты (catalog_id + number)
            stmt = select(UserSticker).where(
                UserSticker.catalog_id == catalog_id,
                UserSticker.number == instance
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                skipped_count += 1
                continue

            # 4. Создаем запись в пуле
            # Собираем NFT адрес если он есть (некоторые стикеры в Thermos могут иметь привязанный адрес)
            nft_address = ts.get("nft_address") or ts.get("address")
            
            new_pool_item = UserSticker(
                catalog_id=catalog_id,
                number=instance,
                is_available=True,
                is_onchain=False, # Всегда False для Thermos по умолчанию, как просил пользователь
                ton_price=catalog.floor_price_ton,
                stars_price=catalog.floor_price_stars,
                nft_address=nft_address,
                owner_id=None
            )
            db.add(new_pool_item)
            added_count += 1

        await db.commit()
        logger.success(f"Pool seed from Thermos completed: added {added_count}, skipped {skipped_count} duplicates.")

if __name__ == "__main__":
    asyncio.run(seed_pool_thermos())
