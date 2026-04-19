import asyncio
import sys
import os
from sqlalchemy import select
from loguru import logger

# Добавляем корень проекта в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import async_session_factory
from app.models.sticker import StickerCatalog
from app.services.thermos_service import thermos_service
from app.core.config import settings

async def sync_thermos_floor():
    """
    Скрипт для сверки флор-прайса с Thermos API.
    Обходит все оффчейн-коллекции в БД и обновляет их цену.
    """
    logger.info("Starting Thermos floor price sync script...")
    
    async with async_session_factory() as db:
        # 1. Получаем все оффчейн коллекции
        query = select(StickerCatalog).where(StickerCatalog.is_onchain == False)
        result = await db.execute(query)
        catalogs = result.scalars().all()
        
        if not catalogs:
            logger.info("No off-chain catalogs found in DB.")
            return

        logger.info(f"Found {len(catalogs)} off-chain catalogs to check.")
        
        # 2. Получаем актуальный каталог от Thermos один раз (для оптимизации)
        thermos_catalog = await thermos_service.get_market_catalog()
        if not thermos_catalog:
            logger.error("Could not fetch Thermos catalog. Check THERMOS_API_TOKEN and network.")
            return

        updated_count = 0
        for catalog in catalogs:
            logger.debug(f"Checking floor for: {catalog.name} (Collection: {catalog.collection_name})")
            
            # Пытаемся найти предмет в каталоге Thermos
            # Используем collection_name или name для поиска
            search_name = catalog.collection_name or catalog.name
            
            # Ищем минимальную цену в полученном каталоге
            matching_prices = []
            for item in thermos_catalog:
                if search_name.lower() in item.get("name", "").lower():
                    price_nano = item.get("price")
                    if price_nano:
                        matching_prices.append(float(price_nano) / 10**9)
            
            if matching_prices:
                new_floor = min(matching_prices)
                old_floor = catalog.floor_price_ton
                
                if old_floor != new_floor:
                    logger.info(f"Price update for {catalog.name}: {old_floor} -> {new_floor} TON")
                    catalog.floor_price_ton = new_floor
                    # Пересчитываем в Stars по текущему курсу
                    catalog.floor_price_stars = round(new_floor / settings.STARS_TO_TON_RATE, 2)
                    db.add(catalog)
                    updated_count += 1
                else:
                    logger.debug(f"Price for {catalog.name} remains unchanged: {new_floor} TON")
            else:
                logger.warning(f"Could not find item '{search_name}' in Thermos catalog.")

        if updated_count > 0:
            await db.commit()
            logger.success(f"Sync completed! Updated {updated_count} catalogs.")
        else:
            logger.info("Sync completed. No updates needed.")

if __name__ == "__main__":
    # Настройка логирования
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    try:
        asyncio.run(sync_thermos_floor())
    except KeyboardInterrupt:
        logger.info("Sync interrupted by user.")
    except Exception as e:
        logger.exception(f"Critical error during sync: {e}")
