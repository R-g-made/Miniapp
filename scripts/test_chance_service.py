import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch
from loguru import logger
from uuid import uuid4

# Add project root to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.chance_service import chance_service
from backend.core.config import settings

async def test_chance_rebalance():
    """
    Тест сервиса перерасчета шансов (ChanceService).
    Проверяет:
    1. Категоризацию айтемов (cheap, medium, expensive).
    2. Перерасчет шансов под 90% RTP.
    3. Автоматическую корректировку цены кейса.
    """
    logger.info("Starting ChanceService test...")

    # 1. Создаем мок данные для кейса
    class MockStickerCatalog:
        def __init__(self, name, floor_price_ton):
            self.name = name
            self.floor_price_ton = floor_price_ton

    class MockCaseItem:
        def __init__(self, id, sticker_catalog_id, chance, price):
            self.id = id
            self.sticker_catalog_id = sticker_catalog_id
            self.chance = chance
            self.sticker_catalog = MockStickerCatalog(f"Sticker {id}", price)

    class MockCase:
        def __init__(self, id, slug, price_ton, is_active, is_chance_distribution):
            self.id = id
            self.slug = slug
            self.price_ton = price_ton
            self.price_stars = round(price_ton / settings.STARS_TO_TON_RATE)
            self.is_active = is_active
            self.is_chance_distribution = is_chance_distribution
            self.items = []

    # Создаем кейс: цена 10 TON, RTP 90% -> Целевой EV = 9 TON
    case_id = uuid4()
    mock_case = MockCase(case_id, "test-case", 10.0, True, True)
    
    # Добавляем 9 айтемов: 3 дешевых, 3 средних, 3 дорогих
    import random as py_random
    
    # Генерируем цены
    prices = (
        [py_random.uniform(0.5, 2.0) for _ in range(3)] +   # Cheap
        [py_random.uniform(5.0, 15.0) for _ in range(3)] +  # Medium
        [py_random.uniform(40.0, 100.0) for _ in range(3)]  # Expensive
    )
    
    mock_case.items = []
    for i, price in enumerate(prices):
        mock_case.items.append(
            MockCaseItem(uuid4(), uuid4(), 1.0/len(prices), price)
        )

    # 2. Настраиваем моки для внешних вызовов
    mock_db = AsyncMock()
    
    # Мокаем crud_sticker.count_available_in_pool (всегда есть в наличии)
    with patch("app.services.chance_service.crud_sticker.count_available_in_pool", return_value=10):
        # Мокаем получение кейса из БД
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_case
        mock_db.execute.return_value = mock_result

        logger.info(f"Initial state: Case price = {mock_case.price_ton} TON")
        for i, item in enumerate(mock_case.items):
            logger.info(f"  Item {i}: Price = {item.sticker_catalog.floor_price_ton} TON, Chance = {item.chance}")

        # 3. Запускаем перерасчет
        logger.info("\nRunning recalculate_case_chances...")
        await chance_service.recalculate_case_chances(mock_db, case_id)

        # 4. Проверяем результаты
        total_chance = sum(item.chance for item in mock_case.items)
        ev = sum(item.chance * item.sticker_catalog.floor_price_ton for item in mock_case.items)
        rtp = (ev / mock_case.price_ton) * 100 if mock_case.price_ton > 0 else 0

        logger.success("\nRebalance results:")
        logger.info(f"Final Case Price: {mock_case.price_ton} TON")
        logger.info(f"Final Case Price (Stars): {mock_case.price_stars}")
        
        for i, item in enumerate(mock_case.items):
            logger.info(f"  Item {i}: Price = {item.sticker_catalog.floor_price_ton} TON, New Chance = {item.chance:.6f}")
        
        logger.info(f"Total Chance: {total_chance:.4f} (should be 1.0)")
        logger.info(f"Expected Value (EV): {ev:.4f} TON")
        logger.info(f"Return to Player (RTP): {rtp:.2f}% (Target 90%)")

        # 5. Тестируем ситуацию, когда все стикеры подорожали (цена кейса должна вырасти)
        logger.info("\nTesting scenario: All stickers became expensive...")
        for item in mock_case.items:
            item.sticker_catalog.floor_price_ton *= 5 # Все подорожали в 5 раз
        
        await chance_service.recalculate_case_chances(mock_db, case_id)
        
        ev_new = sum(item.chance * item.sticker_catalog.floor_price_ton for item in mock_case.items)
        rtp_new = (ev_new / mock_case.price_ton) * 100
        
        logger.success("\nResults after price surge:")
        logger.info(f"Updated Case Price: {mock_case.price_ton} TON")
        logger.info(f"Expected Value (EV): {ev_new:.4f} TON")
        logger.info(f"New RTP: {rtp_new:.2f}%")

if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    try:
        asyncio.run(test_chance_rebalance())
    except Exception as e:
        logger.exception(f"Test failed: {e}")
