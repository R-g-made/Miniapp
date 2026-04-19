import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_bootstrap_en(client: AsyncClient):
    """Тест bootstrap на английском (по умолчанию)"""
    response = await client.get("/api/v1/bootstrap?lang=en")
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "success"
    # Проверяем наличие английских лейблов
    labels = [opt["label"] for opt in data["data"]["dictionaries"]["sorting_options"]]
    assert "Cheapest First" in labels
    assert "Expensive First" in labels

@pytest.mark.asyncio
async def test_bootstrap_ru(client: AsyncClient):
    """Тест bootstrap на русском"""
    response = await client.get("/api/v1/bootstrap?lang=ru")
    assert response.status_code == 200
    data = response.json()
    
    assert data["status"] == "success"
    # Проверяем наличие русских лейблов
    labels = [opt["label"] for opt in data["data"]["dictionaries"]["sorting_options"]]
    assert "Сначала дешевые" in labels
    assert "Сначала дорогие" in labels

@pytest.mark.asyncio
async def test_bootstrap_default_to_en(client: AsyncClient):
    """Тест bootstrap с неизвестным языком (FastAPI должен вернуть 422 из-за Enum)"""
    response = await client.get("/api/v1/bootstrap?lang=fr")
    assert response.status_code == 422
