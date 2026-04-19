import pytest
import random
from unittest.mock import patch

@pytest.mark.asyncio
async def test_login_endpoint(client):
    """Тест эндпоинта /api/v1/auth с рандомным ID"""
    random_id = random.randint(10000000, 99999999)
    login_data = {
        "init_data": "test_init_data"
    }
    
    test_user_data = {
        "id": random_id,
        "first_name": "Test",
        "username": f"user_{random_id}"
    }
    
    # Мокаем парсинг данных, проверку подписи и генерацию payload для кошелька
    with patch("backend.core.security.security_service.parse_init_data", return_value=test_user_data), \
         patch("backend.core.security.security_service.verify_init_data_signature", return_value=True), \
         patch("backend.services.wallet_service.WalletService.generate_ton_proof_payload", return_value="test_payload"):
        
        response = await client.post("/api/v1/auth", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        token_data = data["data"]
        assert "access_token" in token_data
        assert "user" in token_data
        assert token_data["user"]["telegram_id"] == random_id
        assert token_data["ton_proof_payload"] == "test_payload"
