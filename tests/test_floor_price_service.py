import pytest
import pytest_asyncio
import uuid
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.issuer import Issuer
from backend.models.sticker import StickerCatalog, PriorityMarket
from backend.models.case import Case
from backend.services.floor_price_service import floor_price_service
from backend.core.config import settings


@pytest_asyncio.fixture
async def seeded_catalog_data(db: AsyncSession):
    """Создаем тестовые данные для каталога"""
    # Создаем эмитента
    issuer = Issuer(
        name="Test Issuer",
        slug="test-issuer"
    )
    db.add(issuer)
    await db.flush()

    # Создаем несколько каталогов
    catalog1 = StickerCatalog(
        issuer_id=issuer.id,
        name="Cook",
        collection_name="DOGS OG",
        image_url="https://example.com/cook.png",
        floor_price_ton=None,
        floor_price_stars=None,
        priority_market=PriorityMarket.LAFFKA,
        max_pool_size=5
    )

    catalog2 = StickerCatalog(
        issuer_id=issuer.id,
        name="Blue Wings",
        collection_name="Flappy Bird",
        image_url="https://example.com/blue-wings.png",
        floor_price_ton=10.0,
        floor_price_stars=10.0 / settings.STARS_TO_TON_RATE,
        priority_market=PriorityMarket.LAFFKA,
        max_pool_size=5
    )

    db.add(catalog1)
    db.add(catalog2)
    await db.commit()

    await db.refresh(issuer)
    await db.refresh(catalog1)
    await db.refresh(catalog2)

    return issuer, catalog1, catalog2


@pytest.mark.asyncio
async def test_get_pack_floor_ton():
    """Тестируем извлечение цены из данных пакета"""
    test_pack = {
        "current": {"price": {"floor": {"ton": 5.5}}},
        "24h": {"price": {"floor": {"ton": 6.0}}},
        "7d": {"price": {"floor": {"ton": 7.0}}},
        "30d": {"price": {"floor": {"ton": 8.0}}}
    }

    price = floor_price_service._get_pack_floor_ton(test_pack)
    assert price == 5.5

    # Тестируем приоритет
    test_pack_no_current = {
        "24h": {"price": {"floor": {"ton": 6.0}}},
        "7d": {"price": {"floor": {"ton": 7.0}}}
    }
    price = floor_price_service._get_pack_floor_ton(test_pack_no_current)
    assert price == 6.0

    # Тестируем пустые данные
    empty_pack = {}
    price = floor_price_service._get_pack_floor_ton(empty_pack)
    assert price is None


@pytest.mark.asyncio
async def test_should_update_price():
    """Тестируем логику обновления цены с порогом"""
    # Без старой цены - всегда обновляем
    assert floor_price_service._should_update_price(None, 5.0) is True
    assert floor_price_service._should_update_price(0.0, 5.0) is True

    # С порогом 20% (по умолчанию)
    old_price = 10.0
    # Изменение < 20% - не обновляем
    assert floor_price_service._should_update_price(old_price, 11.0) is False
    assert floor_price_service._should_update_price(old_price, 9.0) is False
    # Изменение == 20% - обновляем
    assert floor_price_service._should_update_price(old_price, 12.0) is True
    assert floor_price_service._should_update_price(old_price, 8.0) is True
    # Изменение > 20% - обновляем
    assert floor_price_service._should_update_price(old_price, 15.0) is True


@pytest.mark.asyncio
async def test_update_all_prices_mocked(db: AsyncSession, seeded_catalog_data):
    """Тестируем полный цикл обновления цен с моком внешнего API"""
    issuer, catalog1, catalog2 = seeded_catalog_data

    # Мок данных из stickers.tools
    mock_tools_floors = {
        "DOGS OG": {"Cook": 5.5},
        "Flappy Bird": {"Blue Wings": 12.0}
    }

    # Мок метод _fetch_all_floors_from_tools
    with patch.object(floor_price_service, '_fetch_all_floors_from_tools', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_tools_floors

        # Мок chance_service.recalculate_case_chances
        with patch('backend.services.floor_price_service.chance_service') as mock_chance:
            mock_chance.recalculate_case_chances = AsyncMock()

            # Запускаем обновление
            await floor_price_service.update_all_prices(db)

            # Проверяем, что методы были вызваны
            mock_fetch.assert_called_once()

            # Проверяем обновленные цены в БД
            await db.refresh(catalog1)
            await db.refresh(catalog2)

            assert catalog1.floor_price_ton == 5.5
            assert catalog1.floor_price_stars == 5.5 / settings.STARS_TO_TON_RATE

            # catalog2 имел 10.0, новая цена 12.0 (изменение 20%) - должно обновиться
            assert catalog2.floor_price_ton == 12.0
            assert catalog2.floor_price_stars == 12.0 / settings.STARS_TO_TON_RATE


@pytest.mark.asyncio
async def test_update_all_prices_threshold_not_met(db: AsyncSession, seeded_catalog_data):
    """Тестируем случай, когда изменение цены меньше порога"""
    issuer, catalog1, catalog2 = seeded_catalog_data

    # Установим цену, которая изменится меньше чем на 20%
    catalog2.floor_price_ton = 10.0
    await db.commit()

    mock_tools_floors = {
        "DOGS OG": {"Cook": 5.5},
        "Flappy Bird": {"Blue Wings": 11.0}  # Изменение на 10%
    }

    with patch.object(floor_price_service, '_fetch_all_floors_from_tools', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_tools_floors

        with patch('backend.services.floor_price_service.chance_service') as mock_chance:
            mock_chance.recalculate_case_chances = AsyncMock()

            await floor_price_service.update_all_prices(db)

            await db.refresh(catalog2)
            # Цена не должна измениться
            assert catalog2.floor_price_ton == 10.0


@pytest.mark.asyncio
async def test_update_catalog_price(db: AsyncSession, seeded_catalog_data):
    """Тестируем метод _update_catalog_price"""
    issuer, catalog1, catalog2 = seeded_catalog_data

    new_price = 7.5
    await floor_price_service._update_catalog_price(db, catalog1.id, new_price)

    await db.refresh(catalog1)
    assert catalog1.floor_price_ton == new_price
    assert catalog1.floor_price_stars == new_price / settings.STARS_TO_TON_RATE
