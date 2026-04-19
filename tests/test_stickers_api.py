import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.user import User
from backend.models.issuer import Issuer
from backend.models.sticker import StickerCatalog, UserSticker
from backend.core.security import security_service
from datetime import datetime, timedelta, timezone
import uuid

@pytest_asyncio.fixture
async def seeded_sticker_data(db: AsyncSession):
    # 1. Создаем пользователя
    user = User(
        telegram_id=999888777,
        username="sticker_owner",
        balance_ton=10.0,
        balance_stars=1000.0
    )
    db.add(user)
    await db.flush()

    # 2. Создаем эмитента
    issuer = Issuer(
        name="Test Issuer",
        slug="test-issuer"
    )
    db.add(issuer)
    await db.flush()

    # 3. Создаем каталог стикеров
    catalog_item = StickerCatalog(
        issuer_id=issuer.id,
        name="Rare Sticker",
        image_url="http://example.com/sticker.png",
        floor_price_ton=2.0,
        floor_price_stars=200.0
    )
    db.add(catalog_item)
    await db.flush()

    # 4. Создаем обычный стикер
    user_sticker = UserSticker(
        owner_id=user.id,
        catalog_id=catalog_item.id,
        number=1,
        is_available=True
    )
    db.add(user_sticker)

    # 5. Создаем заблокированный стикер (разблокировка через 24 часа)
    locked_sticker = UserSticker(
        owner_id=user.id,
        catalog_id=catalog_item.id,
        number=2,
        is_available=True,
        unlock_date=datetime.now(timezone.utc) + timedelta(hours=24)
    )
    db.add(locked_sticker)
    
    await db.commit()
    
    token = security_service.create_access_token(subject=user.id)
    
    return user, issuer, catalog_item, user_sticker, locked_sticker, token

@pytest.mark.asyncio
async def test_get_my_stickers_with_locks(client: AsyncClient, seeded_sticker_data):
    user, issuer, catalog, user_sticker, locked_sticker, token = seeded_sticker_data
    headers = {"Authorization": f"Bearer {token}"}
    
    response = await client.get("/api/v1/stickers/my", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    res_data = data["data"]
    assert res_data["total"] == 2
    
    items = {item["number"]: item for item in res_data["items"]}
    
    # Проверяем обычный стикер
    assert items[1]["is_locked"] is False
    assert items[1]["unlock_date"] is None
    
    # Проверяем заблокированный стикер
    assert items[2]["is_locked"] is True
    assert items[2]["unlock_date"] is not None
    # Проверяем формат даты (должна быть строка DD.MM.YYYY HH:MM:SS)
    assert "." in items[2]["unlock_date"]
    assert ":" in items[2]["unlock_date"]

@pytest.mark.asyncio
async def test_sell_sticker_ton(client: AsyncClient, seeded_sticker_data, db: AsyncSession):
    user, issuer, catalog, user_sticker, locked_sticker, token = seeded_sticker_data
    headers = {"Authorization": f"Bearer {token}"}
    
    response = await client.post(
        f"/api/v1/stickers/{user_sticker.id}/sell",
        json={"currency": "ton"},
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    res_data = data["data"]
    assert res_data["currency"].lower() == "ton"
    assert res_data["sold_amount"] == 2.0 * 0.95
    assert res_data["new_balance"] == 10.0 + (2.0 * 0.95)

@pytest.mark.asyncio
async def test_sell_sticker_stars(client: AsyncClient, seeded_sticker_data, db: AsyncSession):
    user, issuer, catalog, user_sticker, locked_sticker, token = seeded_sticker_data
    headers = {"Authorization": f"Bearer {token}"}
    
    response = await client.post(
        f"/api/v1/stickers/{user_sticker.id}/sell",
        json={"currency": "stars"},
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    res_data = data["data"]
    assert res_data["currency"].lower() == "stars"
    assert res_data["sold_amount"] == 200.0 * 0.95
    assert res_data["new_balance"] == 1000.0 + (200.0 * 0.95)

@pytest.mark.asyncio
async def test_sell_non_existent_sticker(client: AsyncClient, seeded_sticker_data):
    user, issuer, catalog, user_sticker, locked_sticker, token = seeded_sticker_data
    headers = {"Authorization": f"Bearer {token}"}
    
    fake_id = uuid.uuid4()
    response = await client.post(
        f"/api/v1/stickers/{fake_id}/sell",
        json={"currency": "ton"},
        headers=headers
    )
    
    assert response.status_code == 404
