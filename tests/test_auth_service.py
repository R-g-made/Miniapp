import pytest
import random
from unittest.mock import patch
from backend.services.auth_service import AuthService
from backend.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_authenticate_new_user(db: AsyncSession):
    """Тест авторизации нового пользователя с рандомным ID"""
    auth_service = AuthService(db)
    random_id = random.randint(10000000, 99999999)
    
    # Мокаем parse_init_data и verify_init_data_signature
    test_user_data = {
        "id": random_id,
        "first_name": "Test",
        "last_name": "User",
        "username": f"user_{random_id}",
        "language_code": "en"
    }
    
    with patch("backend.core.security.security_service.parse_init_data", return_value=test_user_data), \
         patch("backend.core.security.security_service.verify_init_data_signature", return_value=True):
        
        user, token = await auth_service.authenticate_telegram_user("test_init_data")
        
        assert user.telegram_id == random_id
        assert user.username == f"user_{random_id}"
        assert token is not None
        assert user.last_login_at is not None
        
        # Проверяем, что пользователь сохранился в БД
        from backend.crud.user import user_repository
        db_user = await user_repository.get_by_telegram_id(db, random_id)
        assert db_user is not None
        assert db_user.id == user.id
        assert db_user.last_login_at is not None

@pytest.mark.asyncio
async def test_authenticate_existing_user(db: AsyncSession):
    """Тест обновления данных существующего пользователя с рандомным ID"""
    from backend.crud.user import user_repository
    from backend.schemas.user import UserCreate
    
    random_id = random.randint(10000000, 99999999)
    
    # Сначала создаем пользователя вручную
    await user_repository.create_user(db, UserCreate(
        telegram_id=random_id,
        username="old_username",
        full_name="Old Name"
    ))
    
    auth_service = AuthService(db)
    updated_data = {
        "id": random_id,
        "first_name": "New",
        "last_name": "Name",
        "username": "new_username"
    }
    
    with patch("backend.core.security.security_service.parse_init_data", return_value=updated_data), \
         patch("backend.core.security.security_service.verify_init_data_signature", return_value=True):
        
        user, token = await auth_service.authenticate_telegram_user("valid_init_data")
        
        assert user.telegram_id == random_id
        assert user.username == "new_username"
        assert user.full_name == "New Name"
