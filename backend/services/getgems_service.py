import httpx
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
from backend.core.config import settings
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class GetGemsService:
    """
    Сервис для взаимодействия с GetGems API и покупки on-chain NFT.
    """
    def __init__(self):
        self.base_url = settings.GETGEMS_BASE_URL.rstrip("/")
        self.api_token = settings.GETGEMS_API_TOKEN
        self._jwt_token: Optional[str] = None
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
        """Авторизация через токен для получения JWT"""
        logger.info("GetGemsService: Attempting to authenticate...")
        url = f"{self.base_url}/v1/auth/token" # Пример эндпоинта
        try:
            response = await self._client.post(url, json={"token": self.api_token})
            if response.status_code == 200:
                self._jwt_token = response.json().get("access_token")
                return True
            logger.error(f"GetGemsService: Auth failed ({response.status_code}): {response.text}")
        except Exception as e:
            logger.error(f"GetGemsService: Auth request failed: {e}")
        return False

    async def _request(self, method: str, endpoint: str, retry_on_auth: bool = True, **kwargs) -> httpx.Response:
        """Универсальный метод для запросов с JWT и ретриями"""
        if not self._jwt_token:
            await self._auth()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {self._jwt_token}"
        kwargs["headers"] = headers

        response = await self._client.request(method, url, **kwargs)

        if response.status_code == 401 and retry_on_auth:
            logger.warning("GetGemsService: JWT expired, re-authenticating...")
            if await self._auth():
                return await self._request(method, endpoint, retry_on_auth=False, **kwargs)
        
        if response.status_code == 429:
            logger.warning("GetGemsService: Rate limit hit")
            response.raise_for_status()

        return response

    async def get_on_sale_nfts(self, collection_address: str) -> List[Dict[str, Any]]:
        """Получает список NFT на продаже в коллекции"""
        await self._ensure_connected()
        try:
            response = await self._request("GET", f"v1/nfts/on-sale/{collection_address}")
            response.raise_for_status()
            return response.json().get("items", [])
        except Exception as e:
            logger.error(f"GetGemsService: Failed to fetch listings for {collection_address}: {e}")
            return []

    async def get_buy_tx_params(self, nft_address: str) -> Optional[Dict[str, Any]]:
        """Получает параметры транзакции для покупки NFT по фиксированной цене"""
        try:
            response = await self._request("POST", f"v1/nfts/buy-fix-price/{nft_address}")
            response.raise_for_status()
            return response.json() # Ожидаем {'to': ..., 'amount': ..., 'payload': ...}
        except Exception as e:
            logger.error(f"GetGemsService: Failed to get buy params for {nft_address}: {e}")
            return None

    async def execute_ton_transfer(self, to: str, amount_nano: int, payload: str) -> Optional[str]:
        """Выполняет перевод TON через серверный кошелек"""
        try:
            from tonutils.utils import to_nano
            from tonutils.contracts.wallet import WalletV5R1
            
            client = await self._get_ton_client()
            mnemonic_list = settings.NFT_SENDER_MNEMONIC.split()
            wallet, _, _, _ = WalletV5R1.from_mnemonic(client, mnemonic_list)
            
            tx_hash = await wallet.transfer(
                destination=to,
                amount=amount_nano,
                payload=payload
            )
            return tx_hash
        except Exception as e:
            logger.error(f"GetGemsService: Blockchain transfer failed: {e}")
            return None

    async def verify_nft_ownership(self, nft_address: str) -> bool:
        """Проверяет, владеет ли наш серверный кошелек данным NFT"""
        await self._ensure_connected()
        try:
            from tonutils.contracts.wallet import WalletV5R1
            from tonutils.contracts.nft import NFTItemStandard
            
            client = await self._get_ton_client()
            mnemonic_list = settings.NFT_SENDER_MNEMONIC.split()
            wallet, _, _, _ = WalletV5R1.from_mnemonic(client, mnemonic_list)
            our_address = wallet.address.to_str()
            
            # Используем NFTItemStandard для проверки владельца NFT
            nft_item = await NFTItemStandard.from_address(client, nft_address)
            return nft_item.owner_address.to_str() == our_address
        except Exception as e:
            logger.error(f"GetGemsService: Failed to verify NFT ownership for {nft_address}: {e}")
            return False

    async def buy_missing_stickers(self, db: Any, catalog_id: Any, collection_address: str, needed_count: int) -> List[Dict[str, Any]]:
        """Массовая покупка недостающих стикеров через GetGems"""
        logger.info(f"GetGemsService: Auto-buy is currently DISABLED (under development).")
        return []
        
        from backend.crud.sticker import sticker as crud_sticker
        logger.info(f"GetGemsService: Starting auto-buy for {collection_address} (needed: {needed_count})")
        
        nfts_on_sale = await self.get_on_sale_nfts(collection_address)
        # Сортируем по цене (если есть в ответе)
        nfts_on_sale.sort(key=lambda x: int(x.get("price", 0)))
        
        to_buy = nfts_on_sale[:needed_count]
        results = []

        for nft in to_buy:
            nft_address = nft["address"]
            logger.info(f"GetGemsService: Buying NFT {nft_address}")
            
            tx_params = await self.get_buy_tx_params(nft_address)
            if not tx_params:
                continue

            # Выполняем транзакцию
            tx_hash = await self.execute_ton_transfer(
                to=tx_params["to"],
                amount_nano=int(tx_params["amount"]),
                payload=tx_params["payload"]
            )

            if tx_hash:
                logger.info(f"GetGemsService: TX sent, hash: {tx_hash}. Waiting for confirmation...")
                # Ждем немного и проверяем владение
                await asyncio.sleep(10) # Упрощенно
                
                if await self.verify_nft_ownership(nft_address):
                    logger.success(f"GetGemsService: NFT {nft_address} successfully purchased!")
                    
                    price_ton = float(tx_params["amount"]) / 10**9
                    
                    # Записываем в БД
                    await crud_sticker.create(db, obj_in={
                        "catalog_id": catalog_id,
                        "owner_id": None,
                        "is_available": True,
                        "number": nft.get("index", 0),
                        "nft_address": nft_address
                    })
                    
                    # Обновляем флор
                    await crud_sticker.update_catalog_floor_price(
                        db, catalog_id=catalog_id, ton_price=price_ton,
                        stars_price=price_ton / settings.STARS_TO_TON_RATE
                    )
                    
                    results.append({"success": True, "nft_address": nft_address, "tx_hash": tx_hash})
                else:
                    logger.error(f"GetGemsService: NFT {nft_address} purchase confirmation failed.")
                    results.append({"success": False, "nft_address": nft_address, "error": "Verification failed"})
            
            await db.commit()
            
        return results

    async def get_floor_price(self, collection_address: str) -> Optional[float]:
        """Старый метод для обратной совместимости (через GraphQL или новый API)"""
        await self._ensure_connected()
        nfts = await self.get_on_sale_nfts(collection_address)
        if nfts:
            return float(nfts[0].get("price", 0)) / 10**9
        return None

    async def transfer_nft(self, nft_address: str, destination_address: str, price_ton: Optional[float] = None) -> Optional[str]:
        """
        Переводит NFT с серверного кошелька на адрес пользователя.
        Согласно стандарту NFT 2.0 (Telemint/TIP-62)
        - Адрес автора из роялти-параметров (0.01 TON)
        - Адрес фонда из конфига (0.01 TON)
        - Адрес ТГ из конфига (0.01 TON)
        """
        await self._ensure_connected()
        logger.info(f"GetGemsService: Transferring NFT {nft_address} to {destination_address}...")
        
        try:
            from tonutils.utils import to_nano, cell_to_hex
            from tonutils.contracts.wallet import WalletV5R1, TONTransferBuilder
            from tonutils.contracts.nft import NFTItemStandard, NFTCollectionStandard, NFTTransferBody
            
            client = await self._get_ton_client()
            mnemonic_list = settings.NFT_SENDER_MNEMONIC.split()
            wallet, _, _, _ = WalletV5R1.from_mnemonic(client, mnemonic_list)
            our_address = wallet.address.to_str()

            # 1. Получаем данные об NFT один раз
            nft_item = await NFTItemStandard.from_address(client, nft_address)
            
            # 2. Проверка владения
            if nft_item.owner_address.to_str() != our_address:
                logger.error(f"GetGemsService: Transfer failed. Server wallet ({our_address}) does not own NFT {nft_address}")
                return None

            # 3. Получаем адрес роялти автора из коллекции
            royalty_author_address = None
            try:
                collection_address = nft_item.collection_address
                collection = await NFTCollectionStandard.from_address(client, collection_address)
                royalty = await collection.royalty_params()
                
                if royalty and len(royalty) >= 3:
                    author_addr_obj = royalty[2]
                    royalty_author_address = author_addr_obj.to_str() if hasattr(author_addr_obj, "to_str") else str(author_addr_obj)
                    logger.info(f"GetGemsService: Found royalty author address: {royalty_author_address}")
            except Exception as e:
                logger.warning(f"GetGemsService: Could not fetch NFT royalty info: {e}")

            if not royalty_author_address:
                logger.error(f"GetGemsService: Royalty address not found for NFT {nft_address}. Operation cancelled.")
                return None

            # 4. Определение фиксированных сумм (0.01 TON)
            fixed_royalty_nano = to_nano(0.01, 9)
            royalty_fund_address = settings.NFT_FUND_ADDRESS
            royalty_tg_address = settings.NFT_TG_ADDRESS
            
            # 5. Подготовка сообщений для транзакции
            messages = []
            
            # Сообщение 1: Перевод NFT (Standard TIP-4 / NFT 2.0)
            nft_transfer_body = NFTTransferBody(
                destination=destination_address,
                forward_amount=to_nano(0.01, 9), # Минимальное количество TON для форварда (нотис)
                response_address=wallet.address.to_str()
            ).serialize()
            
            messages.append(TONTransferBuilder(
                destination=nft_address,
                amount=to_nano(0.05, 9), # Количество TON для выполнения операции в смарт-контракте
                body=nft_transfer_body
            ))
            
            # Сообщение 2: Отправка автору (0.01 TON) - из метаданных
            if royalty_author_address and royalty_author_address != "EQ...":
                logger.info(f"GetGemsService: Sending 0.01 TON royalty to author (from metadata): {royalty_author_address}")
                messages.append(TONTransferBuilder(
                    destination=royalty_author_address,
                    amount=fixed_royalty_nano
                ))
            
            # Сообщение 3: Отправка фонду (0.01 TON) - из конфига
            if royalty_fund_address and royalty_fund_address != "EQ...":
                logger.info(f"GetGemsService: Sending 0.01 TON royalty to fund (from config): {royalty_fund_address}")
                messages.append(TONTransferBuilder(
                    destination=royalty_fund_address,
                    amount=fixed_royalty_nano
                ))

            # Сообщение 4: Отправка ТГ (0.01 TON) - из конфига
            if royalty_tg_address and royalty_tg_address != "EQ...":
                logger.info(f"GetGemsService: Sending 0.01 TON royalty to TG (from config): {royalty_tg_address}")
                messages.append(TONTransferBuilder(
                    destination=royalty_tg_address,
                    amount=fixed_royalty_nano
                ))
            
            # 4. Отправка мульти-транзакции
            ext_msg = await wallet.batch_transfer_message(messages)
            
            # Получаем хеш транзакции
            if hasattr(ext_msg, "normalized_hash"):
                tx_hash = ext_msg.normalized_hash
            elif hasattr(ext_msg, "hash"):
                tx_hash = ext_msg.hash
            else:
                tx_hash = cell_to_hex(ext_msg.to_cell().hash)
            
            logger.success(f"GetGemsService: NFT 2.0 Transfer initiated. Royalties (0.01 TON each) sent to author, fund, and TG. Hash: {tx_hash}")
            return tx_hash
        except Exception as e:
            logger.error(f"GetGemsService: Failed to transfer NFT {nft_address}: {e}")
            return None

getgems_service = GetGemsService()
