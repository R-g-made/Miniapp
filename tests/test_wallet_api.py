import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, AsyncMock
from backend.models.user import User
from backend.core.security import security_service
import uuid

@pytest_asyncio.fixture
async def seeded_wallet_user(db: AsyncSession):
    # 1. Создаем пользователя
    user = User(
        telegram_id=88877766,
        username="wallet_user",
        balance_ton=0.0,
        balance_stars=0.0
    )
    db.add(user)
    await db.commit()
    
    token = security_service.create_access_token(subject=user.id)
    
    return user, token

@pytest.mark.asyncio
async def test_get_ton_proof_payload(client: AsyncClient, seeded_wallet_user):
    user, token = seeded_wallet_user
    headers = {"Authorization": f"Bearer {token}"}
    
    with patch("app.services.wallet_service.WalletService.generate_ton_proof_payload", return_value="mock_payload_123"):
        response = await client.get("/api/v1/wallet/ton-proof/payload", headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["payload"] == "mock_payload_123"

@pytest.mark.asyncio
async def test_check_ton_proof_success(client: AsyncClient, seeded_wallet_user):
    user, token = seeded_wallet_user
    headers = {"Authorization": f"Bearer {token}"}
    
    check_data = {
        "address": "0:1234567890abcdef",
        "network": "-239",
        "publicKey": "pubkey_hex",
        "proof": {"some": "proof_data"}
    }
    
    with patch("app.services.wallet_service.WalletService.check_ton_proof", return_value=True):
        response = await client.post("/api/v1/wallet/ton-proof/check", json=check_data, headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["address"] == check_data["address"]

@pytest.mark.asyncio
async def test_replenish_ton(client: AsyncClient, seeded_wallet_user):
    user, token = seeded_wallet_user
    headers = {"Authorization": f"Bearer {token}"}
    
    replenish_data = {
        "currency": "TON",
        "amount": 1.5
    }
    
    response = await client.post("/api/v1/wallet/replenish", json=replenish_data, headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    res_data = data["data"]
    assert res_data["ton_transaction"]["amount"] == str(int(1.5 * 10**9))
    assert "transaction_id" in res_data

@pytest.mark.asyncio
async def test_replenish_stars(client: AsyncClient, seeded_wallet_user):
    user, token = seeded_wallet_user
    headers = {"Authorization": f"Bearer {token}"}
    
    replenish_data = {
        "currency": "STARS",
        "amount": 100
    }
    
    with patch("app.services.wallet_service.WalletService.create_stars_invoice", return_value="https://t.me/invoice/link"):
        response = await client.post("/api/v1/wallet/replenish", json=replenish_data, headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    res_data = data["data"]
    assert res_data["payment_url"] == "https://t.me/invoice/link"
    assert "transaction_id" in res_data
