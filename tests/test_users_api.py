import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.user import User
from backend.core.security import security_service
import uuid

@pytest_asyncio.fixture
async def seeded_user_data(db: AsyncSession):
    # 1. Создаем пользователя
    user = User(
        telegram_id=12345678,
        username="test_user",
        full_name="Test User Profile",
        balance_ton=5.0,
        balance_stars=500.0,
        language_code="en"
    )
    db.add(user)
    await db.commit()
    
    token = security_service.create_access_token(subject=user.id)
    
    return user, token

@pytest.mark.asyncio
async def test_read_user_me(client: AsyncClient, seeded_user_data):
    user, token = seeded_user_data
    headers = {"Authorization": f"Bearer {token}"}
    
    response = await client.get("/api/v1/users/me", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    user_data = data["data"]
    assert user_data["telegram_id"] == user.telegram_id
    assert user_data["balance_ton"] == 5.0
    assert user_data["balance_stars"] == 500.0

@pytest.mark.asyncio
async def test_update_user_me_language(client: AsyncClient, seeded_user_data, db: AsyncSession):
    user, token = seeded_user_data
    headers = {"Authorization": f"Bearer {token}"}
    
    # Обновляем язык на русский
    response = await client.patch(
        "/api/v1/users/me",
        json={"language_code": "ru"},
        headers=headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["language_code"] == "ru"
    
    # Проверяем в БД (опционально)
    # await db.refresh(user)
    # assert user.language_code == "ru"

@pytest.mark.asyncio
async def test_read_user_me_unauthorized(client: AsyncClient):
    # Без токена
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401
