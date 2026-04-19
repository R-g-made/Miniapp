import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, MagicMock
from backend.models.user import User
from backend.models.referral import Referral
from backend.core.security import security_service
from backend.core.config import settings
import uuid

@pytest_asyncio.fixture
async def users_with_referrals(db: AsyncSession):
    # 1. Создаем реферера (тот, кто приглашает)
    referrer = User(
        telegram_id=111111111,
        username="referrer_user",
        full_name="Referrer User",
        balance_ton=1.0,
        balance_stars=100.0
    )
    db.add(referrer)
    await db.flush()

    # 2. Создаем реферала (тот, кого пригласили)
    referred = User(
        telegram_id=222222222,
        username="referred_user",
        full_name="Referred User",
        balance_ton=0.0,
        balance_stars=0.0
    )
    db.add(referred)
    await db.flush()

    # 3. Создаем реферальную связь
    referral = Referral(
        referrer_id=referrer.id,
        referred_id=referred.id,
        ref_percentage=5.0, # 5%
        reward_ton=0.5,     # Уже заработал 0.5 TON
        reward_stars_available=50.0,
        reward_stars_locked=10.0
    )
    db.add(referral)
    await db.commit()
    
    # Генерируем токен для реферера
    token = security_service.create_access_token(subject=referrer.id)
    
    return referrer, referred, referral, token

@pytest.mark.asyncio
async def test_get_referral_stats(client: AsyncClient, users_with_referrals):
    referrer, referred, referral, token = users_with_referrals
    headers = {"Authorization": f"Bearer {token}"}
    
    response = await client.get("/api/v1/referrals/stats", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    stats = data["data"]
    
    assert stats["referral_code"] == str(referrer.telegram_id)
    assert stats["total_invited"] == 1
    assert stats["ton"]["total_earned"] == 0.5
    assert stats["ton"]["available_balance"] == 1.0
    assert stats["stars"]["total_earned"] == 60.0 # 50 + 10
    assert stats["stars"]["available_balance"] == 100.0
    assert stats["stars"]["locked_balance"] == 10.0

@pytest.mark.asyncio
async def test_withdraw_referral_success(client: AsyncClient, db: AsyncSession, users_with_referrals):
    referrer, referred, referral, token = users_with_referrals
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Привязываем кошелек (новое требование)
    from backend.models.wallet import Wallet
    wallet = Wallet(owner_id=referrer.id, address="EQC__________________________________________", is_active=True)
    db.add(wallet)
    await db.commit()
    
    mock_result = {
        "status": "success",
        "transaction_id": str(uuid.uuid4()),
        "hash": "mock_hash",
        "amount": 0.5,
        "address": "EQC__________________________________________"
    }
    
    with patch("app.services.referral_service.ReferralService.withdraw_ton", return_value=mock_result):
        # Пытаемся вывести 0.5 TON
        response = await client.post(
            "/api/v1/referrals/withdraw",
            json={
                "amount": 0.5,
                "address": "EQC__________________________________________"
            },
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        # Проверяем, что лишних полей нет
        assert "hash" not in data
        assert "amount" not in data

@pytest.mark.asyncio
async def test_get_referral_stats_no_referrals(client: AsyncClient, db: AsyncSession):
    # Создаем пользователя без рефералов
    user = User(
        telegram_id=333333333,
        username="lonely_user",
        balance_ton=0.0
    )
    db.add(user)
    await db.commit()
    
    token = security_service.create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}
    
    response = await client.get("/api/v1/referrals/stats", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    stats = data["data"]
    assert stats["total_invited"] == 0
    assert stats["ton"]["total_earned"] == 0.0
    assert stats["stars"]["total_earned"] == 0.0
