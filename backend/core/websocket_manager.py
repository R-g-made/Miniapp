import json
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import WebSocket
from backend.core.redis import redis_service
from backend.core.config import settings
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
        self.pubsub_task: Optional[asyncio.Task] = None

    async def _setup_pubsub(self):
        """Подписка на канал в Redis для получения сообщений от других процессов"""
        if not settings.USE_REDIS:
            return
            
        try:
            redis_client = await redis_service.connect()
            pubsub = redis_client.pubsub()
            await pubsub.subscribe("ws_events")
            
            logger.info("WS Manager: Subscribed to Redis channel 'ws_events'")
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    target_user_id = data.get("target_user_id")
                    message_obj = WSEventMessage(**data["message"])
                    
                    if target_user_id:
                        await self._local_send_to_user(target_user_id, message_obj)
                    else:
                        await self._local_broadcast(message_obj)
        except Exception as e:
            logger.error(f"WS Manager: Redis Pub/Sub error: {e}")
            await asyncio.sleep(5)
            # Рекурсивный перезапуск при ошибке
            asyncio.create_task(self._setup_pubsub())

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        user_id_str = str(user_id)
        if user_id_str not in self.active_connections:
            self.active_connections[user_id_str] = []
        self.active_connections[user_id_str].append(websocket)
        logger.debug(f"WS Manager: New connection for user {user_id_str}. Total: {len(self.active_connections[user_id_str])}")
        
        # Запускаем pubsub при первом подключении, когда цикл событий уже запущен
        if not self.pubsub_task and settings.USE_REDIS:
            self.pubsub_task = asyncio.create_task(self._setup_pubsub())
        
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
        """Отправить сообщение ВСЕМ подключенным пользователям (через Redis если включен)"""
        if settings.USE_REDIS:
            redis_client = await redis_service.connect()
            payload = json.dumps({
                "target_user_id": None,
                "message": message.model_dump()
            })
            await redis_client.publish("ws_events", payload)
        else:
            await self._local_broadcast(message)

    async def send_to_user(self, user_id: str, message: WSEventMessage):
        """Отправить персональное сообщение пользователю (через Redis если включен)"""
        if settings.USE_REDIS:
            redis_client = await redis_service.connect()
            payload = json.dumps({
                "target_user_id": str(user_id),
                "message": message.model_dump()
            })
            await redis_client.publish("ws_events", payload)
        else:
            await self._local_send_to_user(user_id, message)

    async def _local_broadcast(self, message: WSEventMessage):
        """Внутренний метод для локальной рассылки"""
        payload = message.model_dump_json()
        for user_id, user_connections in self.active_connections.items():
            for websocket in user_connections:
                try:
                    await websocket.send_text(payload)
                except Exception as e:
                    logger.warning(f"WS Manager: Failed local broadcast to {user_id}: {e}")
                    continue

    async def _local_send_to_user(self, user_id: str, message: WSEventMessage):
        """Внутренний метод для локальной отправки пользователю"""
        user_id_str = str(user_id)
        if user_id_str in self.active_connections:
            payload = message.model_dump_json()
            for websocket in self.active_connections[user_id_str]:
                try:
                    await websocket.send_text(payload)
                except Exception as e:
                    logger.warning(f"WS Manager: Failed local direct send to {user_id_str}: {e}")
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