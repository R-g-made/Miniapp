import pytest
import pytest_asyncio
import random
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.case import Case
from backend.models.issuer import Issuer
from backend.models.sticker import StickerCatalog
from backend.models.associations import CaseItem, CaseIssuer
from backend.models.user import User
from backend.core.security import security_service
import uuid

@pytest_asyncio.fixture
async def seeded_data(db: AsyncSession):
    # 1. Создаем эмитента
    issuer = Issuer(
        slug="test-issuer",
        name="Test Issuer",
        icon_url="http://example.com/icon.png"
    )
    db.add(issuer)
    await db.flush()

    # 2. Создаем стикер в каталоге
    catalog_item = StickerCatalog(
        issuer_id=issuer.id,
        name="Test Sticker",
        image_url="http://example.com/sticker.png",
        floor_price_ton=1.0,
        floor_price_stars=100
    )
    db.add(catalog_item)
    await db.flush()

    # 3. Создаем кейс
    case = Case(
        slug="test-case",
        name="Test Case",
        image_url="http://example.com/case.png",
        price_ton=2.0,
        price_stars=200,
        is_active=True
    )
    db.add(case)
    await db.flush()

    # 4. Связываем кейс с эмитентом и стикером
    case_issuer = CaseIssuer(case_id=case.id, issuer_id=issuer.id, is_main=True)
    case_item = CaseItem(case_id=case.id, sticker_catalog_id=catalog_item.id, chance=1.0)
    db.add(case_issuer)
    db.add(case_item)
    
    await db.commit()
    return case, issuer, catalog_item

@pytest_asyncio.fixture
async def auth_user(db: AsyncSession):
    user = User(
        telegram_id=123456789,
        username="testuser",
        full_name="Test User",
        balance_ton=10.0,
        balance_stars=1000.0
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    token = security_service.create_access_token(subject=user.id)
    return user, token

@pytest.mark.asyncio
async def test_get_cases(client: AsyncClient, seeded_data):
    response = await client.get("/api/v1/cases")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) >= 1
    assert data["data"][0]["slug"] == "test-case"

@pytest.mark.asyncio
async def test_get_case_by_slug(client: AsyncClient, seeded_data):
    response = await client.get("/api/v1/cases/test-case")
    assert response.status_code == 200
    data = response.json()
    # Теперь данные в поле data
    assert "data" in data
    assert data["data"]["slug"] == "test-case"
    assert data["data"]["price_ton"] == 2.0
    assert len(data["data"]["items"]) == 1

@pytest.mark.asyncio
async def test_open_case_success(client: AsyncClient, db: AsyncSession, seeded_data, auth_user):
    user, token = auth_user
    headers = {"Authorization": f"Bearer {token}"}
    
    response = await client.post(
        "/api/v1/cases/test-case/open",
        json={"currency": "ton"},
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "data" in data
    assert "drop" in data["data"]
    assert data["data"]["new_balance"] == 8.0 # 10.0 - 2.0
    assert data["data"]["currency"].lower() == "ton"
    
    # Проверяем обновление аналитики в БД
    await db.refresh(user)
    assert user.total_cases_opened == 1
    assert user.total_spent_ton == 2.0

@pytest.mark.asyncio
async def test_open_case_insufficient_funds(client: AsyncClient, db: AsyncSession, seeded_data):
    # Создаем бедного пользователя
    user = User(
        telegram_id=random.randint(10000000, 99999999),
        username="pooruser",
        balance_ton=0.1,
        balance_stars=0
    )
    db.add(user)
    await db.commit()
    
    token = security_service.create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}
    
    response = await client.post(
        "/api/v1/cases/test-case/open",
        json={"currency": "ton"},
        headers=headers
    )
    
    # В приложении ошибки возвращаются через JSONResponse(status_code=400, content={"message": "..."})
    # или через хендлеры, которые могут возвращать {"detail": "..."}
    assert response.status_code == 400 
    error_data = response.json()
    assert "message" in error_data or "detail" in error_data
    message = error_data.get("message") or error_data.get("detail")
    assert "Insufficient funds" in message

@pytest.mark.asyncio
async def test_get_non_existent_case(client: AsyncClient):
    response = await client.get("/api/v1/cases/non-existent")
    assert response.status_code == 404
