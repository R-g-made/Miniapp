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
from backend.core.config import settings


async def test_real_floor_catalog():
    """Тест реального получения флоров и сопоставления с каталогом из БД"""
    logger.info("=== Тест реального флора для каталога ===")

    # 1. Получаем все стикеры из БД
    async with async_session_factory() as db:
        catalogs = await crud_sticker.get_all_catalogs(db)
        logger.info(f"Получено {len(catalogs)} стикеров из каталога")

        if len(catalogs) == 0:
            logger.error("Каталог пуст! Сначала запусти seed скрипты.")
            return

        # Показываем первые несколько стикеров
        logger.info("\nПримеры стикеров из каталога:")
        for i, cat in enumerate(catalogs[:10]):
            logger.info(f"{i+1}. {cat.name} [{cat.collection_name}] - текущий флор: {cat.floor_price_ton} TON")

    # 2. Получаем реальные флоры из stickers.tools
    logger.info("\nПолучаем флоры из stickers.tools...")
    all_floors = await floor_price_service._fetch_all_floors_from_tools()

    if not all_floors:
        logger.error("Не удалось получить флоры из stickers.tools")
        return

    logger.success(f"Получены флоры для {len(all_floors)} коллекций")

    # 3. Сопоставляем
    logger.info("\n=== Результаты сопоставления ===")

    found_count = 0
    not_found_count = 0
    matched = []
    not_matched = []

    async with async_session_factory() as db:
        catalogs = await crud_sticker.get_all_catalogs(db)

        for cat in catalogs:
            col_name = cat.collection_name
            pack_name = cat.name

            if col_name in all_floors and pack_name in all_floors[col_name]:
                found_count += 1
                price = all_floors[col_name][pack_name]
                matched.append({
                    "name": pack_name,
                    "collection": col_name,
                    "old_price": cat.floor_price_ton,
                    "new_price": price
                })
            else:
                not_found_count += 1
                not_matched.append({
                    "name": pack_name,
                    "collection": col_name
                })

    # Показываем результат
    logger.info(f"✅ Найдено: {found_count}")
    logger.info(f"❌ Не найдено: {not_found_count}")

    if matched:
        logger.info("\n📋 Найденные стикеры и их флоры:")
        for item in matched:
            old = f"{item['old_price']:.4f}" if item['old_price'] else "None"
            logger.info(f"  - {item['name']} [{item['collection']}]: {old} → {item['new_price']:.4f} TON")

    if not_matched:
        logger.warning("\n⚠️  Не найденные стикеры:")
        for item in not_matched[:20]:  # показываем первые 20
            logger.warning(f"  - {item['name']} [{item['collection']}]")
        if len(not_matched) > 20:
            logger.warning(f"  ... и еще {len(not_matched) - 20}")

    # 4. Тест обновления цены с реальными данными (но не коммитим в БД)
    logger.info("\n=== Тест логики обновления ===")
    if matched:
        test_item = matched[0]
        old = test_item['old_price']
        new = test_item['new_price']
        should_update = floor_price_service._should_update_price(old, new)

        logger.info(f"Тест для {test_item['name']}:")
        logger.info(f"  Старая цена: {old}")
        logger.info(f"  Новая цена: {new}")
        logger.info(f"  Нужно обновить? {should_update}")

    logger.success("\n=== Тест завершен ===")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")

    try:
        asyncio.run(test_real_floor_catalog())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"Ошибка: {e}")
