import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from loguru import logger
from backend.core.config import settings

class ThermosService:
    """
    Сервис для взаимодействия с Thermos API (https://backend.thermos.gifts).
    Используется исключительно для перевода (трансфера) оффчейн-стикеров (Gifts).
    """
    def __init__(self):
        self.base_url = settings.THERMOS_BASE_URL
        self.api_token = settings.THERMOS_API_TOKEN
        self._jwt_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _get_jwt_token(self) -> str:
        """Получает или обновляет JWT токен через API токен (валиден 24 часа)"""
        now = datetime.now(timezone.utc)
        
        # Если токен есть и он еще валиден (с запасом 5 минут)
        if self._jwt_token and self._token_expires_at and now < self._token_expires_at - timedelta(minutes=5):
            return self._jwt_token

        logger.info("ThermosService: Authenticating with API token...")
        url = f"{self.base_url}/auth/api-token"
        params = {"api_token": self.api_token}
        
        try:
            response = await self._client.post(url, params=params)
            if response.status_code != 200:
                logger.error(f"ThermosService: Auth failed ({response.status_code}): {response.text}")
                response.raise_for_status()
                
            data = response.json()
            self._jwt_token = data.get("token")
            # Токен валиден 24 часа по умолчанию
            self._token_expires_at = now + timedelta(hours=24)
            logger.success("ThermosService: JWT token obtained successfully")
            return self._jwt_token
        except Exception as e:
            logger.error(f"ThermosService: Failed to get JWT token: {e}")
            raise

    async def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Универсальный метод для запросов с автоматическим обновлением токена"""
        token = await self._get_jwt_token()
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        kwargs["headers"] = headers

        response = await self._client.request(method, url, **kwargs)
        
        # Если токен протух (401), сбрасываем его и пробуем еще раз
        if response.status_code == 401:
            logger.warning("ThermosService: JWT expired (401), retrying auth...")
            self._jwt_token = None
            token = await self._get_jwt_token()
            headers["Authorization"] = f"Bearer {token}"
            response = await self._client.request(method, url, **kwargs)
            
        return response

    async def get_my_stickers(self) -> List[Dict[str, Any]]:
        """Получает список моих стикеров на аккаунте Thermos"""
        logger.debug("ThermosService: Fetching owned stickers (/stickers/me)...")
        try:
            # Пытаемся вызвать /stickers/me
            response = await self._request("GET", "stickers/me")
            
            # Если 404, возможно эндпоинт другой (например /gifts/me)
            if response.status_code == 404:
                logger.warning("ThermosService: /stickers/me not found, trying /gifts/me")
                response = await self._request("GET", "gifts/me")
            
            response.raise_for_status()
            data = response.json()
            # Обычно возвращается список или объект с полем stickers/gifts
            if isinstance(data, list):
                return data
            return data.get("stickers") or data.get("gifts") or []
        except Exception as e:
            logger.error(f"ThermosService: Failed to fetch owned stickers: {e}")
            return None

    async def transfer_sticker(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Перевод (трансфер) стикера другому пользователю или вывод на аккаунт.
        payload: {
            "owned_stickers": [{"collection_id": int, "character_id": int, "instance": int}],
            "withdraw": bool,
            "target_telegram_user_id": int,
            ...
        }
        """
        logger.info(f"ThermosService: Transferring sticker to TG ID {payload.get('target_telegram_user_id')}...")
        try:
            response = await self._request("POST", "stickers/transfer", json=payload)
            if response.status_code != 200:
                logger.error(f"ThermosService: Transfer failed with status {response.status_code}: {response.text}")
            response.raise_for_status()
            data = response.json()
            logger.success("ThermosService: Transfer request successful")
            return data
        except Exception as e:
            # Если это ошибка httpx с ответом, логируем тело
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"ThermosService: API Error Details: {e.response.text}")
            logger.error(f"ThermosService: Transfer exception: {e}")
            raise

thermos_service = ThermosService()
