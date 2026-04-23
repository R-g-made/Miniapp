import sys
import os
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

# Проверяем аргументы командной строки до импортов бэкенда
if "--sqlite" in sys.argv:
    os.environ["USE_SQLITE"] = "True"
    os.environ["USE_REDIS"] = "False"
    print("--- SQLITE & NO-REDIS MODE ENABLED ---")

import asyncio
from loguru import logger

# Импортируем функции сидинга из соседних файлов
from scripts.seed.seed_issuers import seed_issuers
from scripts.seed.seed_catalog import seed_catalog
from scripts.seed.seed_thermos import seed_thermos_mapping
from scripts.seed.seed_case import seed_case
from scripts.seed.seed_pool_thermos import seed_pool_thermos
from scripts.seed.seed_pool_onchain import seed_pool_onchain

from backend.core.config import settings
from backend.db.session import engine, async_session_factory
from backend.models.base import Base
from backend.services.floor_price_service import floor_price_service
from backend.services.chance_service import chance_service
from backend.crud.case import case as crud_case
import backend.models # Ensure all models are imported for metadata

async def main():
    logger.info("=== Starting full database seed from MD files and APIs ===")
    
    # Force SQLite for test seeding if needed
    # settings.USE_SQLITE = True 
    
    try:
        # 0. Инициализация таблиц (особенно для SQLite)
        logger.info(f"Initializing database tables (Database: {settings.async_database_url})")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized.")

        # 1. Сначала сидим эмитентов (нужны для каталога и кейсов)
        logger.info("Step 1: Seeding Issuers...")
        await seed_issuers()
        
        # 2. Сидим каталог стикеров (нужен для маппингов и предметов кейсов)
        logger.info("Step 2: Seeding Sticker Catalog...")
        await seed_catalog()
        
        # 3. Сбор флор-прайсов для всех стикеров
        logger.info("Step 3: Fetching Floor Prices for all stickers...")
        async with async_session_factory() as db:
            await floor_price_service.update_all_prices(db)
        logger.success("Floor prices updated successfully.")
        
        # 4. Сидим маппинг Thermos (нужен для синхронизации цен)
        logger.info("Step 4: Seeding Thermos Mappings...")
        await seed_thermos_mapping()
        
        # 5. Сидим кейсы и их содержимое
        logger.info("Step 5: Seeding Cases and Case Items...")
        await seed_case()
        
        # 6. Пополняем пул стикеров из Thermos
        logger.info("Step 6: Seeding Sticker Pool from Thermos API...")
        await seed_pool_thermos()
        
        # 7. Пополняем пул стикеров из блокчейна (On-chain)
        logger.info("Step 7: Seeding Sticker Pool from Blockchain...")
        await seed_pool_onchain()

        # 8. Перерасчет шансов и цен для всех кейсов на основе актуального флора и пула
        logger.info("Step 8: Smart rebalancing cases chances and prices...")
        async with async_session_factory() as db:
            all_cases = await crud_case.get_multi(db, limit=1000)
            for case_obj in all_cases:
                logger.info(f"Rebalancing case: {case_obj.slug}")
                await chance_service.recalculate_case_chances(db, case_obj.id)
        logger.success("Smart rebalancing completed.")
        
        logger.info("=== Full seed completed successfully! ===")
    except Exception as e:
        logger.error(f"Error during full seed: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())
