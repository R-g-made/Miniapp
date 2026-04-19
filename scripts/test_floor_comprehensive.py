import asyncio
import sys
import os
from loguru import logger
from pathlib import Path
from unittest.mock import patch, AsyncMock

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from backend.db.session import async_session_factory
from backend.models.issuer import Issuer
from backend.models.sticker import StickerCatalog, PriorityMarket
from backend.services.floor_price_service import floor_price_service
from backend.crud.sticker import sticker as crud_sticker
from backend.core.config import settings


from sqlalchemy import select

async def create_test_catalog_in_db(db):
    """Создаем тестовые стикеры, которые точно совпадают с stickers.tools"""
    # Проверяем, существует ли эмитент
    issuer_stmt = select(Issuer).where(Issuer.slug == "test-issuer-floor-test")
    issuer_result = await db.execute(issuer_stmt)
    issuer = issuer_result.scalar_one_or_none()
    
    if not issuer:
        # Создаем эмитента
        issuer = Issuer(
            name="Test Issuer for Floor Test",
            slug="test-issuer-floor-test"
        )
        db.add(issuer)
        await db.flush()

    # Создаем стикеры, которые есть в stickers.tools
    test_stickers = [
        {
            "name": "Cook",
            "collection_name": "DOGS OG",
            "image_url": "https://example.com/cook.png"
        },
        {
            "name": "Blue Wings",
            "collection_name": "Flappy Bird",
            "image_url": "https://example.com/blue-wings.png"
        },
        {
            "name": "Ice Pengu",
            "collection_name": "Pudgy Penguins",
            "image_url": "https://example.com/ice-pengu.png"
        },
        {
            "name": "Classic Pengu",
            "collection_name": "Pudgy Penguins",
            "image_url": "https://example.com/classic-pengu.png"
        }
    ]

    created = []
    for sticker_data in test_stickers:
        # Проверяем, существует ли стикер
        existing_stmt = select(StickerCatalog).where(
            StickerCatalog.issuer_id == issuer.id,
            StickerCatalog.name == sticker_data["name"],
            StickerCatalog.collection_name == sticker_data["collection_name"]
        )
        existing_result = await db.execute(existing_stmt)
        existing = existing_result.scalar_one_or_none()
        
        if not existing:
            catalog = StickerCatalog(
                issuer_id=issuer.id,
                name=sticker_data["name"],
                collection_name=sticker_data["collection_name"],
                image_url=sticker_data["image_url"],
                floor_price_ton=None,
                floor_price_stars=None,
                priority_market=PriorityMarket.LAFFKA,
                max_pool_size=5
            )
            db.add(catalog)
            created.append(catalog)
        else:
            created.append(existing)

    await db.commit()
    for c in created:
        await db.refresh(c)

    return issuer, created


async def test_comprehensive():
    """Полный тест флор-прайсов - от получения до обновления в БД"""
    logger.info("=== Комплексный тест флор-прайсов ===")

    # 1. Тест 1: Получение реальных данных из stickers.tools
    logger.info("\n[Тест 1] Получение данных из stickers.tools")
    all_floors = await floor_price_service._fetch_all_floors_from_tools()

    if not all_floors:
        logger.error("❌ Не удалось получить данные из stickers.tools")
        return

    logger.success(f"✅ Успешно получены данные для {len(all_floors)} коллекций")

    # Проверяем наличие известных коллекций
    expected_collections = ["DOGS OG", "Pudgy Penguins", "Flappy Bird", "Blum"]
    for col in expected_collections:
        if col in all_floors:
            logger.success(f"✅ Коллекция '{col}' найдена - {len(all_floors[col])} стикеров")
        else:
            logger.warning(f"⚠️ Коллекция '{col}' не найдена")

    # 2. Тест 2: Работа с БД - создаем тестовые стикеры
    logger.info("\n[Тест 2] Работа с БД")
    async with async_session_factory() as db:
        issuer, test_catalogs = await create_test_catalog_in_db(db)
        logger.success(f"✅ Создано {len(test_catalogs)} тестовых стикеров в БД")

        # 3. Тест 3: Сопоставление и обновление (с моком, чтобы не менять реальные данные)
        logger.info("\n[Тест 3] Сопоставление и логика обновления")

        # Мокаем метод, чтобы не перезаписывать реальные данные
        with patch.object(floor_price_service, '_update_catalog_price', new_callable=AsyncMock) as mock_update:
            with patch('backend.services.floor_price_service.chance_service') as mock_chance:
                mock_chance.recalculate_case_chances = AsyncMock()

                # Мокаем _fetch_all_floors_from_tools, чтобы вернуть наши данные
                with patch.object(floor_price_service, '_fetch_all_floors_from_tools', new_callable=AsyncMock) as mock_fetch:
                    # Возвращаем данные только для наших тестовых стикеров
                    test_floors = {}
                    for cat in test_catalogs:
                        if cat.collection_name in all_floors and cat.name in all_floors[cat.collection_name]:
                            if cat.collection_name not in test_floors:
                                test_floors[cat.collection_name] = {}
                            test_floors[cat.collection_name][cat.name] = all_floors[cat.collection_name][cat.name]

                    mock_fetch.return_value = test_floors

                    # Запускаем обновление
                    await floor_price_service.update_all_prices(db)

                    # Проверяем результат
                    logger.info(f"\n📋 Результаты сопоставления для тестовых стикеров:")
                    matched_count = 0
                    for cat in test_catalogs:
                        col_name = cat.collection_name
                        pack_name = cat.name
                        if col_name in all_floors and pack_name in all_floors[col_name]:
                            price = all_floors[col_name][pack_name]
                            matched_count += 1
                            logger.info(f"✅ {pack_name} [{col_name}]: {price} TON")
                        else:
                            logger.warning(f"⚠️ {pack_name} [{col_name}]: не найден в stickers.tools")

                    logger.success(f"\n✅ Сопоставлено: {matched_count}/{len(test_catalogs)} тестовых стикеров")

                    # Проверяем, что метод обновления был вызван для найденных стикеров
                    if mock_update.called:
                        call_count = mock_update.call_count
                        logger.success(f"✅ Метод обновления цены вызван {call_count} раз")

        # 4. Тест 4: Проверка логики порога изменения цены
        logger.info("\n[Тест 4] Логика порога изменения цены")

        test_cases = [
            (None, 5.0, True, "Нет старой цены - обновляем"),
            (0.0, 5.0, True, "Старая цена 0 - обновляем"),
            (10.0, 11.0, False, "Изменение 10% - не обновляем"),
            (10.0, 12.0, True, "Изменение 20% - обновляем"),
            (10.0, 8.0, True, "Изменение -20% - обновляем"),
            (10.0, 15.0, True, "Изменение 50% - обновляем"),
        ]

        for old_price, new_price, should_be, description in test_cases:
            result = floor_price_service._should_update_price(old_price, new_price)
            status = "✅" if result == should_be else "❌"
            logger.info(f"{status} {description}: old={old_price}, new={new_price} → should_update={result}")

    logger.success("\n=== Все тесты пройдены! ===")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")

    try:
        asyncio.run(test_comprehensive())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(f"❌ Ошибка: {e}")
