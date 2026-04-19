import pytest
import json
from unittest.mock import patch
from app.core.security import security_service
from app.schemas.websocket import WSMessageType
from app.models.enums import WSMessageType as EnumWSMessageType

def test_websocket_unauthorized(ws_client):
    """Тест подключения к WebSocket с невалидным токеном"""
    with ws_client.websocket_connect("/api/v1/ws/events?token=invalid_token") as websocket:
        # Ждем сообщение об ошибке
        data = websocket.receive_json()
        assert data["type"] == EnumWSMessageType.ERROR
        assert data["data"]["message"] == "Unauthorized"

def test_websocket_connection_success(ws_client):
    """Тест успешного подключения к WebSocket с валидным токеном"""
    user_id = "test-user-id"
    access_token = security_service.create_access_token(subject=user_id)
    
    with ws_client.websocket_connect(f"/api/v1/ws/events?token={access_token}") as websocket:
        # ПОРЯДОК: Сначала история из manager.connect, потом AUTH_SUCCESS из эндпоинта
        
        # 1. Если есть история, она придет первой
        data = websocket.receive_json()
        if data["type"] == EnumWSMessageType.LIVE_DROP:
            # Пропускаем историю, если она есть
            while data["type"] == EnumWSMessageType.LIVE_DROP:
                data = websocket.receive_json()
        
        # 2. Сообщение об успешной авторизации
        assert data["type"] == EnumWSMessageType.AUTH_SUCCESS
        assert data["data"]["user_id"] == user_id

def test_websocket_live_drop_history(ws_client):
    """Тест получения истории Live Drop при подключении"""
    user_id = "test-user-id"
    access_token = security_service.create_access_token(subject=user_id)
    
    # Мокаем историю Live Drop
    mock_history = [
        {"image_url": "test1.png", "floor_price_ton": 1.0},
        {"image_url": "test2.png", "floor_price_ton": 2.0}
    ]
    
    with patch("app.services.live_drop_service.live_drop_service.get_history", return_value=mock_history):
        with ws_client.websocket_connect(f"/api/v1/ws/events?token={access_token}") as websocket:
            # ПОРЯДОК: Сначала история из manager.connect, потом AUTH_SUCCESS из эндпоинта
            
            # 1. История (reversed(history) -> test2, потом test1)
            drop2 = websocket.receive_json()
            assert drop2["type"] == EnumWSMessageType.LIVE_DROP
            assert drop2["data"]["image_url"] == "test2.png"
            
            drop1 = websocket.receive_json()
            assert drop1["type"] == EnumWSMessageType.LIVE_DROP
            assert drop1["data"]["image_url"] == "test1.png"
            
            # 2. Затем AUTH_SUCCESS
            auth_data = websocket.receive_json()
            assert auth_data["type"] == EnumWSMessageType.AUTH_SUCCESS
            assert auth_data["data"]["user_id"] == user_id

def test_ws_message_type_case_insensitivity():
    """Тест нечувствительности WSMessageType к регистру"""
    assert EnumWSMessageType("live_drop") == EnumWSMessageType.LIVE_DROP
    assert EnumWSMessageType("LIVE_DROP") == EnumWSMessageType.LIVE_DROP
    assert EnumWSMessageType("Live_Drop") == EnumWSMessageType.LIVE_DROP
    assert EnumWSMessageType("error") == EnumWSMessageType.ERROR
    assert EnumWSMessageType("AUTH_SUCCESS") == EnumWSMessageType.AUTH_SUCCESS
