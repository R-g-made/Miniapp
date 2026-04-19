import asyncio
import sys
import os
from loguru import logger
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from backend.services.floor_price_service import floor_price_service


async def debug_stickers_tools():
    """Отладочный скрипт - показываем структуру данных от stickers.tools"""
    logger.info("=== Отладка данных от stickers.tools ===")

    all_floors = await floor_price_service._fetch_all_floors_from_tools()

    if not all_floors:
        logger.error("Нет данных")
        return

    logger.success(f"Всего коллекций: {len(all_floors)}")

    # Показываем все коллекции
    logger.info("\n📋 Список всех коллекций:")
    for i, col_name in enumerate(sorted(all_floors.keys()), 1):
        packs = all_floors[col_name]
        logger.info(f"{i:2d}. {col_name} - {len(packs)} стикеров")

    # Показываем первые 5 коллекций с их стикерами
    logger.info("\n🔍 Детали первых 5 коллекций:")
    for i, (col_name, packs) in enumerate(list(all_floors.items())[:5], 1):
        logger.info(f"\n{i}. Коллекция: '{col_name}'")
        for pack_name, price in sorted(packs.items()):
            logger.info(f"   - '{pack_name}': {price} TON")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")

    try:
        asyncio.run(debug_stickers_tools())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Ошибка: {e}")
