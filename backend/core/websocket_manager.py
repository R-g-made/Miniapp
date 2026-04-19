import json
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import WebSocket
from backend.core.redis import redis_service
from backend.schemas.websocket import WSEventMessage, WSMessageType
from loguru import logger

class ConnectionManager:
    """
    Менеджер WebSocket-соединений.
    ВРЕМЕННО: Использует in-memory broadcast вместо Redis для тестов.
    """
    def __init__(self):
        # Храним активные соединения: {user_id: [WebSocket, ...]}
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        user_id_str = str(user_id)
        if user_id_str not in self.active_connections:
            self.active_connections[user_id_str] = []
        self.active_connections[user_id_str].append(websocket)
        logger.debug(f"WS Manager: New connection for user {user_id_str}. Total: {len(self.active_connections[user_id_str])}")
        
        from backend.services.live_drop_service import live_drop_service
        
        history = await live_drop_service.get_history()
        if history:
            logger.debug(f"WS Manager: Sending live drop history ({len(history)} items) to user {user_id_str}")
            for drop in reversed(history):
                message = WSEventMessage(
                    type=WSMessageType.LIVE_DROP,
                    data=drop
                )
                await websocket.send_text(message.model_dump_json())

    def disconnect(self, websocket: WebSocket, user_id: str):
        user_id_str = str(user_id)
        if user_id_str in self.active_connections:
            if websocket in self.active_connections[user_id_str]:
                self.active_connections[user_id_str].remove(websocket)
            if not self.active_connections[user_id_str]:
                del self.active_connections[user_id_str]
        logger.debug(f"WS Manager: Disconnected websocket for user {user_id_str}")

    # --- Публичные методы для отправки событий ---

    async def broadcast(self, message: WSEventMessage):
        """Отправить сообщение ВСЕМ подключенным пользователям (in-memory)"""
        payload = message.model_dump_json()
        logger.debug(f"WS Manager: Broadcasting message {message.type}")
        for user_id, user_connections in self.active_connections.items():
            for websocket in user_connections:
                try:
                    await websocket.send_text(payload)
                except Exception as e:
                    logger.warning(f"WS Manager: Failed broadcast to {user_id}: {e}")
                    continue

    async def send_to_user(self, user_id: str, message: WSEventMessage):
        """Отправить персональное сообщение пользователю (in-memory)"""
        user_id_str = str(user_id)
        if user_id_str in self.active_connections:
            payload = message.model_dump_json()
            logger.debug(f"WS Manager: Sending {message.type} to user {user_id_str}")
            for websocket in self.active_connections[user_id_str]:
                try:
                    await websocket.send_text(payload)
                except Exception as e:
                    logger.warning(f"WS Manager: Failed direct send to {user_id_str}: {e}")
                    continue

    async def listen_and_deliver(self, websocket: WebSocket, user_id: str):
        """
        Заглушка для цикла прослушивания (теперь доставка идет напрямую через broadcast/send_to_user).
        """
        try:
            while True:
                # Просто держим соединение открытым
                await asyncio.sleep(1)
        except Exception:
            pass

manager = ConnectionManager()