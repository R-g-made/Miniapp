import json
from datetime import datetime, timezone
from typing import List, Dict, Any
from backend.core.redis import redis_service
from backend.core.websocket_manager import manager
from backend.schemas.websocket import WSEventMessage, WSMessageType
from loguru import logger

class LiveDropService:
    """
    Сервис для управления историей Live Drop
    """
    REDIS_KEY = "live_drops_history"
    MAX_HISTORY = 10
    
    def __init__(self):
        self._in_memory_history: List[Dict[str, Any]] = []

    async def add_drop(self, image_url: str, floor_price_ton: float = 0.0):
        """
        Добавляет новый дроп в историю и рассылает его всем по WebSocket.
        """
        drop_data = {
            "image_url": image_url,
            "floor_price_ton": floor_price_ton,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        logger.debug(f"LiveDropService: Adding new drop: {image_url} ({floor_price_ton} TON)")
        
        self._in_memory_history.insert(0, drop_data)
        if len(self._in_memory_history) > self.MAX_HISTORY:
            self._in_memory_history = self._in_memory_history[:self.MAX_HISTORY]

        try:
            redis_client = await redis_service.connect()
            await redis_client.lpush(self.REDIS_KEY, json.dumps(drop_data))
            await redis_client.ltrim(self.REDIS_KEY, 0, self.MAX_HISTORY - 1)
        except Exception as e:
            logger.warning(f"LiveDropService: Redis error while adding drop: {e}")
        
        message = WSEventMessage(
            type=WSMessageType.LIVE_DROP,
            data=drop_data
        )
        await manager.broadcast(message)
        logger.info(f"LiveDropService: New drop broadcasted: {image_url}")

    async def get_history(self) -> List[Dict[str, Any]]:
        """
        Возвращает последние 10 дропов из истории.
        """
        logger.debug("LiveDropService: Fetching drops history...")
        try:
            redis_client = await redis_service.connect()
            raw_history = await redis_client.lrange(self.REDIS_KEY, 0, self.MAX_HISTORY - 1)
            if raw_history:
                history = [json.loads(item) for item in raw_history]
                self._in_memory_history = history
                return history
        except Exception as e:
            logger.warning(f"LiveDropService: Redis error while fetching history: {e}. Using in-memory fallback.")
            
        return self._in_memory_history

live_drop_service = LiveDropService()