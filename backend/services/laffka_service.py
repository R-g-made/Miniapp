import httpx
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
from backend.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class LaffkaService:
    """
    Сервис для интеграции с маркетплейсом Laffka (https://laffka-app.shop).
    Реализует авторизацию через Telegram initData, получение листингов и покупку.
    """
    def __init__(self):
        self.base_url = settings.LAFFKA_BASE_URL.rstrip("/")
        self.init_data = settings.LAFFKA_INIT_DATA
        self.ref_code = settings.LAFFKA_REF_CODE
        self._token: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=30.0)
        self._ton_client = None
        
    async def _get_ton_client(self):
        if self._ton_client is None:
            from tonutils.clients import TonapiClient
            self._ton_client = TonapiClient(
                api_key=settings.TON_API_KEY, 
                network='testnet' if settings.IS_TESTNET else 'mainnet'
            )
        return self._ton_client

    async def _ensure_connected(self):
        client = await self._get_ton_client()
        if not client.connected:
            await client.connect()

    async def _auth(self) -> bool:
        """
        Авторизация через Telegram WebApp initData.
        Получает JWT токен для последующих запросов.
        """
        logger.info("LaffkaService: Attempting to authenticate...")
        url = f"{self.base_url}/api/v1/auth/telegram"
        
        payload = {
            "init_data": self.init_data,
            "ref_code": self.ref_code
        }
        
        try:
            response = await self._client.post(url, json=payload)
            if response.status_code == 200:
                self._token = response.json().get("token")
                logger.info("LaffkaService: Authentication successful")
                return True
            logger.error(f"LaffkaService: Auth failed ({response.status_code}): {response.text}")
            return False
        except Exception as e:
            logger.error(f"LaffkaService: Auth request failed: {e}")
            return False

    async def _request(self, method: str, endpoint: str, retry_on_auth: bool = True, **kwargs) -> httpx.Response:
        """Универсальный метод для запросов с JWT и ретриями"""
        if not self._token:
            await self._auth()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {self._token}"
        kwargs["headers"] = headers

        response = await self._client.request(method, url, **kwargs)

        if response.status_code == 401 and retry_on_auth:
            logger.warning("LaffkaService: JWT expired, re-authenticating...")
            if await self._auth():
                return await self._request(method, endpoint, retry_on_auth=False, **kwargs)
        
        if response.status_code == 429:
            logger.warning("LaffkaService: Rate limit hit")
            response.raise_for_status()

        return response

    async def get_listings(self, sticker_id: Optional[str] = None, collection_address: Optional[str] = None, sort: str = "price-low-high") -> Dict[str, Any]:
        """Получает список листингов для стикера или коллекции"""
        try:
            if sticker_id:
                endpoint = f"api/v1/stickers/{sticker_id}/listings"
                params = {"sort": sort}
            elif collection_address:
                endpoint = f"api/v1/collections/{collection_address}/listings"
                params = {"sort": sort}
            else:
                return {"items": []}
                
            response = await self._request("GET", endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"LaffkaService: Failed to fetch listings: {e}")
            return {"items": []}

    async def get_floor_price(self, collection_address: str) -> Optional[float]:
        """Получает флор-цену для коллекции"""
        try:
            data = await self.get_listings(collection_address=collection_address, sort="price-low-high")
            items = data.get("items", [])
            if items:
                return float(items[0].get("price", 0)) / 10**9
            return None
        except Exception as e:
            logger.error(f"LaffkaService: Failed to fetch floor price for {collection_address}: {e}")
            return None

    async def buy_missing_stickers(self, db: Any, catalog_id: Any, sticker_id: str, count: int) -> List[Dict[str, Any]]:
        """Массовая покупка недостающих стикеров через Laffka"""
        logger.info(f"LaffkaService: Starting bulk purchase for {sticker_id} (count: {count})")
        results = []
        
        try:
            listings = await self.get_listings(sticker_id=sticker_id, sort="price-low-high")
            items = listings.get("items", [])
            
            if not items:
                logger.warning(f"LaffkaService: No listings found for sticker {sticker_id}")
                return [{"error": "No listings found"} for _ in range(count)]
                
            # Берем первые N самых дешевых листингов
            to_buy = items[:count]
            
            for item in to_buy:
                try:
                    # TODO: Реализовать реальную покупку через Laffka API
                    # Сейчас это мок, чтобы не тратить деньги
                    logger.info(f"LaffkaService: Would buy listing {item.get('id')} for {item.get('price')} nanoTON")
                    results.append({"success": True, "listing_id": item.get("id")})
                except Exception as e:
                    logger.error(f"LaffkaService: Failed to buy listing {item.get('id')}: {e}")
                    results.append({"error": str(e)})
                    
        except Exception as e:
            logger.error(f"LaffkaService: Bulk purchase failed: {e}")
            return [{"error": str(e)} for _ in range(count)]
            
        return results

    async def withdraw_nft(self, sticker_uuid: str, destination_address: str) -> bool:
        """Выводит ончейн-NFT на внешний кошелек"""
        logger.info(f"LaffkaService: Withdrawing NFT {sticker_uuid} to {destination_address}")
        try:
            # TODO: Реализовать реальный вывод через Laffka API
            # Сейчас это мок
            return True
        except Exception as e:
            logger.error(f"LaffkaService: NFT withdrawal failed: {e}")
            return False

    async def withdraw_sticker(self, sticker_uuid: str) -> bool:
        """Выводит офчейн-стикер из Laffka"""
        logger.info(f"LaffkaService: Withdrawing sticker {sticker_uuid}")
        try:
            # TODO: Реализовать реальный вывод через Laffka API
            # Сейчас это мок
            return True
        except Exception as e:
            logger.error(f"LaffkaService: Sticker withdrawal failed: {e}")
            return False

laffka_service = LaffkaService()
