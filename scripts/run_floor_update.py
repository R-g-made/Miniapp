import asyncio
import sys
import os
from loguru import logger
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from backend.db.session import async_session_factory
from backend.services.floor_price_service import floor_price_service
from backend.crud.sticker import sticker as crud_sticker


async def run_floor_update():
    """Запускаем обновление флор-прайсов вручную и смотрим логи"""
    logger.info("=== Запуск обновления флор-прайсов ===")

    async with async_session_factory() as db:
        # 1. Показываем текущее состояние каталога
        logger.info("\n[1/4] Текущее состояние каталога:")
        catalogs = await crud_sticker.get_all_catalogs(db)
        
        logger.info(f"Всего стикеров: {len(catalogs)}")
        
        # Показываем первые 20
        for i, cat in enumerate(catalogs[:20], 1):
            logger.info(f"{i:2d}. {cat.name} [{cat.collection_name}] - флор: {cat.floor_price_ton} TON")

        # 2. Получаем данные из stickers.tools
        logger.info("\n[2/4] Получаем данные из stickers.tools...")
        all_floors = await floor_price_service._fetch_all_floors_from_tools()
        
        if not all_floors:
            logger.error("❌ Не удалось получить данные")
            return
        
        logger.success(f"✅ Данные получены для {len(all_floors)} коллекций")

        # 3. Проверяем сопоставление
        logger.info("\n[3/4] Проверка сопоставления:")
        found = []
        not_found = []
        
        for cat in catalogs:
            col = cat.collection_name
            name = cat.name
            if col in all_floors and name in all_floors[col]:
                found.append({
                    "cat": cat,
                    "price": all_floors[col][name]
                })
            else:
                not_found.append(cat)
        
        logger.info(f"✅ Найдено: {len(found)}")
        logger.info(f"❌ Не найдено: {len(not_found)}")
        
        if found:
            logger.info("\n📋 Найденные стикеры:")
            for item in found[:20]:
                cat = item["cat"]
                old = cat.floor_price_ton
                new = item["price"]
                logger.info(f"  - {cat.name} [{cat.collection_name}]: {old} → {new} TON")
        
        if not_found:
            logger.warning("\n⚠️ Не найденные (первые 20):")
            for cat in not_found[:20]:
                logger.warning(f"  - {cat.name} [{cat.collection_name}]")

        # 4. Запускаем обновление
        logger.info("\n[4/4] Запускаем обновление...")
        await floor_price_service.update_all_prices(db)
        
        # Проверяем результат
        logger.info("\n[Результат] После обновления:")
        catalogs_after = await crud_sticker.get_all_catalogs(db)
        
        updated_count = 0
        for cat in catalogs_after:
            if cat.floor_price_ton is not None and cat.floor_price_ton > 0:
                updated_count += 1
        
        logger.success(f"✅ Обновлено стикеров с флором: {updated_count}")
        
        for i, cat in enumerate([c for c in catalogs_after if c.floor_price_ton is not None][:20], 1):
            logger.info(f"{i:2d}. {cat.name} [{cat.collection_name}] - флор: {cat.floor_price_ton} TON")

    logger.success("\n=== Обновление завершено! ===")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    try:
        asyncio.run(run_floor_update())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"❌ Ошибка: {e}")
