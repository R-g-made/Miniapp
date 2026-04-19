import httpx
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
from backend.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tonutils.utils import to_nano
from tonutils.clients import TonapiClient

from tonutils.contracts.wallet import WalletV5R1

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
        self._ton_client = TonapiClient(
            api_key=settings.TON_API_KEY, 
            network='testnet' if settings.IS_TESTNET else 'mainnet'
        )

    async def _ensure_connected(self):
        if not self._ton_client.connected:
            await self._ton_client.connect()

    async def _auth(self) -> bool:
        """
        Авторизация через Telegram WebApp initData.
        Получает JWT токен для последующих запросов.
        """
        logger.info("LaffkaService: Attempting to authenticate...")
        url = f"{self.base_url}/api/v1/auth/telegram"
        
        payload = {
            "initData": self.init_data
        }
        if self.ref_code:
            payload["refCode"] = self.ref_code

        try:
            response = await self._client.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                self._token = data.get("access_token")
                if self._token:
                    logger.success("LaffkaService: Successfully authenticated.")
                    return True
                else:
                    logger.error("LaffkaService: Auth response missing access_token.")
            else:
                logger.error(f"LaffkaService: Auth failed with status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"LaffkaService: Auth request failed: {e}")
        
        return False

    async def _request(self, method: str, endpoint: str, retry_on_auth: bool = True, **kwargs) -> httpx.Response:
        """
        Универсальный метод для запросов с автоматической авторизацией и рефрешем токена.
        """
        await self._ensure_connected()
        if not self._token:
            success = await self._auth()
            if not success:
                raise Exception("LaffkaService: Authentication failed, cannot proceed with request.")

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {self._token}"
        kwargs["headers"] = headers

        response = await self._client.request(method, url, **kwargs)

        # Обработка Rate Limit (429) для механизмов повторов (tenacity)
        if response.status_code == 429:
            logger.warning(f"LaffkaService: Rate limit hit (429) on {endpoint}")
            response.raise_for_status()

        # Если 401 и мы еще не пробовали переавторизоваться
        if response.status_code == 401 and retry_on_auth:
            logger.warning("LaffkaService: Received 401 Unauthorized, re-authenticating...")
            success = await self._auth()
            if success:
                # Повторяем запрос с новым токеном, retry_on_auth=False чтобы не зациклиться
                return await self._request(method, endpoint, retry_on_auth=False, **kwargs)
            else:
                logger.error("LaffkaService: Re-authentication failed.")

        return response

    async def get_listings(
        self, 
        cursor: Optional[str] = None,
        collection_id: Optional[str] = None,
        sticker_id: Optional[str] = None,
        sort: str = "time-latest",
        is_liquidation: Optional[bool] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получает активные листинги маркета с пагинацией и фильтрами.
        """
        params = {"sort": sort}
        if cursor: params["cursor"] = cursor
        if collection_id: params["collection_id"] = collection_id
        if sticker_id: params["sticker_id"] = sticker_id
        if is_liquidation is not None: params["is_liquidation"] = str(is_liquidation).lower()
        if search: params["search"] = search

        try:
            response = await self._request("GET", "api/v1/market/listings", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"LaffkaService: Failed to fetch listings: {e}")
            return {"items": [], "next_cursor": None}

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True
    )
    async def purchase_listing(self, listing_id: str) -> Dict[str, Any]:
        """
        Покупает стикер из активного листинга.
        Использует tenacity для обработки Rate Limit и временных сбоев.
        """
        logger.info(f"LaffkaService: Attempting to purchase listing {listing_id}...")
        try:
            response = await self._request("POST", f"api/v1/market/purchase/{listing_id}")
            response.raise_for_status()
            data = response.json()
            logger.success(f"LaffkaService: Successfully purchased listing {listing_id}!")
            return data
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning(f"LaffkaService: Rate limit during purchase of {listing_id}, retrying...")
                raise e
            error_data = e.response.json() if e.response.content else {}
            logger.error(f"LaffkaService: Purchase failed with status {e.response.status_code}: {error_data}")
            return {"error": error_data.get("detail", "Unknown error"), "status": e.response.status_code}
        except Exception as e:
            logger.error(f"LaffkaService: Unexpected error during purchase: {e}")
            return {"error": str(e), "status": 500}

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True
    )
    async def withdraw_sticker(self, sticker_uuid: str) -> bool:
        """
        Вывод стикера на стикербот.
        """
        logger.info(f"LaffkaService: Attempting to withdraw sticker {sticker_uuid}...")
        url = "api/v1/sp/withdraw"
        payload = {"sticker_uuid": sticker_uuid}
        
        try:
            response = await self._request("POST", url, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get("ok"):
                logger.success(f"LaffkaService: Successfully withdrawn sticker {sticker_uuid}")
                return True
            logger.error(f"LaffkaService: Withdraw failed for {sticker_uuid}: {data}")
            return False
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise e
            logger.error(f"LaffkaService: Withdraw request failed: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"LaffkaService: Unexpected error during withdraw: {e}")
            return False

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        reraise=True
    )
    async def withdraw_nft(self, sticker_id: str, to_address: str) -> bool:
        """
        Вывод NFT на указанный адрес.
        """
        logger.info(f"LaffkaService: Attempting to withdraw NFT {sticker_id} to {to_address}...")
        url = "api/v1/users/withdraw-nft"
        payload = {
            "sticker_id": sticker_id,
            "to_address": to_address
        }
        
        try:
            response = await self._request("POST", url, json=payload)
            response.raise_for_status()
            data = response.json()
            # Предполагаем, что успех возвращается в поле 'ok' или аналогичном
            if data.get("ok") or data.get("status") == "success":
                logger.success(f"LaffkaService: NFT withdraw request sent for {sticker_id}")
                return True
            logger.error(f"LaffkaService: NFT Withdraw failed for {sticker_id}: {data}")
            return False
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise e
            logger.error(f"LaffkaService: NFT Withdraw request failed: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"LaffkaService: Unexpected error during NFT withdraw: {e}")
            return False

    async def verify_nft_arrival(self, collection_address: str, timeout: int = 60, interval: int = 10) -> Optional[str]:
        """
        Проверяет появление нового NFT из коллекции на нашем кошельке.
        Возвращает адрес нового NFT или None.
        """
        logger.info(f"LaffkaService: Waiting for NFT from collection {collection_address} to arrive...")
        our_address = settings.WALLET_ADDRESS
        
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                # Используем прямой вызов API tonapi через провайдера
                # tonutils.clients.TonapiClient.provider.send_http_request
                response = await self._ton_client.provider.send_http_request(
                    "GET",
                    f"/accounts/{our_address}/nfts",
                    params={"limit": 10}
                )
                
                nft_items = response.get("nft_items", [])
                
                for nft in nft_items:
                    # В ответе tonapi.io/v2/accounts/{address}/nfts структура такая:
                    # nft_items: [ { address: ..., collection: { address: ... } } ]
                    nft_coll = nft.get("collection", {})
                    nft_coll_addr = nft_coll.get("address")
                    
                    if nft_coll_addr == collection_address:
                        actual_addr = nft.get("address")
                        logger.success(f"LaffkaService: New NFT found! Address: {actual_addr}")
                        return actual_addr
                
            except Exception as e:
                logger.error(f"LaffkaService: Error during NFT arrival verification: {e}")
            
            await asyncio.sleep(interval)
            
        logger.warning(f"LaffkaService: NFT from collection {collection_address} did not arrive within {timeout}s")
        return None

    async def buy_missing_stickers(self, db: Any, catalog_id: Any, laffka_sticker_id: str, needed_count: int) -> List[Dict[str, Any]]:
        """
        Поиск, покупка и автоматический вывод недостающих стикеров.
        Заполняет StickerUser (UserSticker) и обновляет цены в каталоге.
        """
        logger.info(f"LaffkaService: Auto-buy is currently DISABLED (under development).")
        return []

        from backend.crud.sticker import sticker as crud_sticker
        from backend.models.sticker import UserSticker, StickerCatalog
        from sqlalchemy import select

        logger.info(f"LaffkaService: Starting bulk process for {laffka_sticker_id} (needed: {needed_count})")
        
        # Получаем данные каталога для адреса коллекции
        stmt = select(StickerCatalog).where(StickerCatalog.id == catalog_id)
        res = await db.execute(stmt)
        catalog = res.scalar_one_or_none()
        collection_address = catalog.collection_address if catalog else None
        
        listing_ids = []
        cursor = None
        
        # 1. Сбор листинг ID
        while len(listing_ids) < needed_count:
            data = await self.get_listings(sticker_id=laffka_sticker_id, sort="price-low-high", cursor=cursor)
            items = data.get("items", [])
            if not items: break
                
            for item in items:
                listing_ids.append(item["id"])
                if len(listing_ids) >= needed_count: break
            
            cursor = data.get("next_cursor")
            if not cursor or len(listing_ids) >= needed_count: break
        
        # 2. Покупка и обработка результатов
        results = []
        for l_id in listing_ids:
            purchase_data = await self.purchase_listing(l_id)
            if "error" in purchase_data:
                results.append(purchase_data)
                continue
            
            # 3. Обработка успешной покупки
            try:
                # Извлекаем данные из ответа
                # UUID для вывода берется из sticker.id согласно требованиям
                sticker_obj = purchase_data.get("sticker", {})
                sticker_uuid = sticker_obj.get("id") or purchase_data.get("id")
                sticker_type = sticker_obj.get("sticker_type") # "onchain" или "offchain"
                
                price_ton = float(purchase_data.get("price", 0)) / 10**9
                serial_number = purchase_data.get("serial_number", 0)
                
                # 4. Обновляем StickerCatalog (ton_price и stars_price)
                await crud_sticker.update_catalog_floor_price(
                    db, 
                    catalog_id=catalog_id,
                    ton_price=price_ton,
                    stars_price=price_ton / settings.STARS_TO_TON_RATE,
                    commit=False
                )
                
                nft_address = purchase_data.get("id") # Фолбэк на UUID покупки для оффчейн
                is_onchain_instance = False
                
                # 5. Обработка вывода
                if sticker_type == "onchain":
                    # Если ончейн, запускаем вывод NFT на наш кошелек из .env
                    # sticker_uuid уже взят из sticker.id (или id) выше
                    success = await self.withdraw_nft(str(sticker_uuid), settings.WALLET_ADRESS)
                    if success and collection_address:
                        # Ждем и проверяем приход NFT
                        actual_nft_address = await self.verify_nft_arrival(collection_address)
                        if actual_nft_address:
                            nft_address = actual_nft_address
                            is_onchain_instance = True
                        else:
                            # Если не пришло, пробуем через обычный стикерпак как фолбэк (по требованию)
                            logger.warning(f"LaffkaService: NFT arrival verification failed for {sticker_uuid}, falling back to stickerpack.")
                            await self.withdraw_sticker(str(sticker_uuid))
                    else:
                        # Если вывод NFT не удался, фолбэк на стикерпак
                        await self.withdraw_sticker(str(sticker_uuid))
                else:
                    # Оффчейн стикер - обычный вывод
                    await self.withdraw_sticker(str(sticker_uuid))
                
                # 6. Создаем UserSticker в нашей БД
                await crud_sticker.create(db, obj_in={
                    "catalog_id": catalog_id,
                    "owner_id": None, # Система
                    "is_available": True,
                    "is_onchain": is_onchain_instance,
                    "number": serial_number,
                    "nft_address": nft_address,
                })
                
                results.append(purchase_data)
                await db.commit()
            except Exception as e:
                logger.error(f"LaffkaService: Error processing purchase {l_id}: {e}")
                await db.rollback()
                results.append({"error": str(e), "listing_id": l_id})
            
        return results

laffka_service = LaffkaService()
