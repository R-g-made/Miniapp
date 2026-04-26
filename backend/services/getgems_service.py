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
        self.api_key = settings.GETGEMS_API_TOKEN
        self._client = httpx.AsyncClient(timeout=30.0)
        self._ton_client = None
        
    async def _get_ton_client(self):
        if self._ton_client is None:
            from tonutils.clients import TonapiClient
            
            network_id = -3 if settings.IS_TESTNET else -239
            base_url = "https://testnet.tonapi.io/v2" if settings.IS_TESTNET else "https://tonapi.io/v2"
            
            self._ton_client = TonapiClient(
                api_key=settings.TON_API_KEY, 
                network=network_id, 
                base_url=base_url
            )
        return self._ton_client

    async def _ensure_connected(self):
        client = await self._get_ton_client()
        if not client.connected:
            await client.connect()

    async def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        """Универсальный метод для запросов с API Key и стандартными заголовками"""
        url = f"{self.base_url}/public-api/{endpoint.lstrip('/')}"
        headers = kwargs.get("headers", {})
        
        # Прямая авторизация через API Key как в curl примере
        if self.api_key:
            headers["Authorization"] = self.api_key
            
        # Стандартные заголовки
        headers.update({
            "accept": "application/json",
            "User-Agent": "PostmanRuntime/7.32.3"
        })
        
        kwargs["headers"] = headers
        return await self._client.request(method, url, **kwargs)

    async def get_on_sale_nfts(self, collection_address: str) -> List[Dict[str, Any]]:
        """Получает список NFT на продаже в коллекции"""
        await self._ensure_connected()
        try:
            params = {"limit": 100}
            response = await self._request("GET", f"v1/nfts/on-sale/{collection_address}", params=params)
            response.raise_for_status()
            
            data = response.json()
            # Согласно структуре API: response -> items
            items = data.get("response", {}).get("items", [])
            return items
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
            from ton_core import to_nano
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

    async def get_floor_price_from_items(self, collection_address: str, name_filter: Optional[str] = None) -> Optional[float]:
        """
        Получает флор-прайс коллекции через эндпоинт Getgems: /v1/nfts/on-sale/{collectionAddress}
        Берет самый дешевый предмет в коллекции (общий флор).
        """
        try:
            # Используем базовый метод запроса
            response = await self._request("GET", f"v1/nfts/on-sale/{collection_address}", params={"limit": 50})
            
            if response.status_code == 200:
                data = response.json()
                inner_data = data.get("response", {})
                items = inner_data.get("items", [])
                
                if items:
                    valid_prices = []
                    for item in items:
                        # Цена в GetGems API находится в sale.fullPrice (в нанотонах)
                        sale = item.get("sale", {})
                        price_nano = sale.get("fullPrice") or item.get("price")
                        
                        if price_nano:
                            try:
                                valid_prices.append(int(price_nano))
                            except (ValueError, TypeError):
                                continue
                    
                    if valid_prices:
                        # Самая низкая цена в коллекции
                        min_price_nano = min(valid_prices)
                        # Переводим нанотоны в тоны (10^9)
                        price_ton = float(min_price_nano) / 1_000_000_000
                        logger.info(f"GetGemsService: Found floor for {collection_address}: {price_ton} TON")
                        return price_ton
            
            logger.warning(f"GetGemsService: No items on sale found for collection {collection_address}")
            return None
        except Exception as e:
            logger.error(f"GetGemsService: Error fetching floor from {collection_address}: {e}")
            return None

    # async def get_floor_price(self, collection_address: str) -> Optional[float]:
    #     """Старый метод для обратной совместимости (через GraphQL или новый API)"""
    #     await self._ensure_connected()
    #     nfts = await self.get_on_sale_nfts(collection_address)
    #     if nfts:
    #         return float(nfts[0].get("price", 0)) / 10**9
    #     return None

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
            from ton_core import to_nano, Address, begin_cell
            from tonutils.contracts.wallet import WalletV5R1, TONTransferBuilder
            from tonutils.contracts.nft import NFTItemStandard, NFTCollectionStandard
            
            client = await self._get_ton_client()
            mnemonic_list = settings.NFT_SENDER_MNEMONIC.split()
            wallet, _, _, _ = WalletV5R1.from_mnemonic(client, mnemonic_list)
            
            # Проверка баланса кошелька отправителя
            account_info = await client.get_info(wallet.address.to_str())
            balance = int(account_info.balance) if hasattr(account_info, 'balance') else 0
            logger.info(f"GetGemsService: Server wallet {wallet.address.to_str()} balance: {balance / 10**9} TON")
            
            if balance < to_nano(0.1, 9): # Минимум 0.1 TON для газа и роялти
                logger.error("GetGemsService: Insufficient server wallet balance")
                return None

            # 1. Получаем данные об NFT
            nft_item = await NFTItemStandard.from_address(client, nft_address)
            
            # 2. Проверка владения (сравниваем как объекты Address)
            our_addr_obj = Address(wallet.address.to_str())
            owner_addr_obj = Address(nft_item.owner_address.to_str())
            
            if our_addr_obj.to_str(is_user_friendly=False) != owner_addr_obj.to_str(is_user_friendly=False):
                logger.error(f"GetGemsService: Transfer failed. Server wallet does not own NFT {nft_address}. Owner: {owner_addr_obj.to_str()}")
                return None

            # 3. Получаем адрес роялти автора из коллекции (опционально)
            royalty_author_address = None
            try:
                collection_address = nft_item.collection_address
                if collection_address:
                    collection = await NFTCollectionStandard.from_address(client, collection_address)
                    royalty = await collection.royalty_params()
                    
                    if royalty and len(royalty) >= 3:
                        author_addr_obj = royalty[2]
                        royalty_author_address = author_addr_obj.to_str() if hasattr(author_addr_obj, "to_str") else str(author_addr_obj)
                        logger.info(f"GetGemsService: Found royalty author address: {royalty_author_address}")
            except Exception as e:
                logger.warning(f"GetGemsService: Could not fetch NFT royalty info (skipping author royalty): {e}")

            # 4. Определение фиксированных сумм (0.01 TON)
            fixed_royalty_nano = to_nano(0.01, 9)
            royalty_fund_address = settings.NFT_FUND_ADDRESS
            royalty_tg_address = settings.NFT_TG_ADDRESS
            
            # 5. Подготовка сообщений для транзакции
            messages = []
            
            # Сообщение 1: Перевод NFT (Standard TIP-4 / Telemint)
            # Конструируем тело сообщения вручную, так как NFTTransferBody может отсутствовать в некоторых версиях tonutils
            # Op: 0x5fcc3d14 (transfer), query_id: 0
            nft_transfer_body = (
                begin_cell()
                .store_uint(0x5fcc3d14, 32)  # op::transfer
                .store_uint(0, 64)           # query_id
                .store_address(Address(destination_address)) # new_owner
                .store_address(Address(wallet.address.to_str())) # response_destination
                .store_maybe_ref(None)       # custom_payload
                .store_coins(to_nano(0.01, 9)) # forward_amount
                .store_maybe_ref(None)       # forward_payload
                .end_cell()
            )
            
            messages.append(TONTransferBuilder(
                destination=nft_address,
                amount=to_nano(0.05, 9), # Количество TON для выполнения операции (газ)
                body=nft_transfer_body
            ))
            
            # Сообщение 2: Отправка автору (0.01 TON) - если нашли адрес
            if royalty_author_address and not royalty_author_address.startswith("EQ0000000000000000000000000000000000000000000000"):
                logger.info(f"GetGemsService: Adding 0.01 TON royalty for author: {royalty_author_address}")
                messages.append(TONTransferBuilder(
                    destination=royalty_author_address,
                    amount=fixed_royalty_nano
                ))
            
            # Сообщение 3: Отправка фонду (0.01 TON) - если адрес в конфиге валиден
            if royalty_fund_address and len(royalty_fund_address) > 10:
                logger.info(f"GetGemsService: Adding 0.01 TON royalty for fund: {royalty_fund_address}")
                messages.append(TONTransferBuilder(
                    destination=royalty_fund_address,
                    amount=fixed_royalty_nano
                ))

            # Сообщение 4: Отправка ТГ (0.01 TON) - если адрес в конфиге валиден
            if royalty_tg_address and len(royalty_tg_address) > 10:
                logger.info(f"GetGemsService: Adding 0.01 TON royalty for TG: {royalty_tg_address}")
                messages.append(TONTransferBuilder(
                    destination=royalty_tg_address,
                    amount=fixed_royalty_nano
                ))
            
            # 6. Отправка мульти-транзакции
            logger.info(f"GetGemsService: Sending batch transfer with {len(messages)} messages")
            
            # Создаем внешнее сообщение (external message) для кошелька V5
            ext_msg = await wallet.create_transfer_message(messages)
            
            # Отправляем сообщение в блокчейн через клиент
            await client.send_message(ext_msg)
            
            # Хеш транзакции можно получить из сообщения
            tx_hash = ext_msg.hash.hex()
            
            if tx_hash:
                logger.success(f"GetGemsService: NFT 2.0 Transfer initiated. Hash: {tx_hash}")
                return tx_hash
            else:
                logger.error("GetGemsService: Failed to get transaction hash")
                return None
                
        except Exception as e:
            logger.exception(f"GetGemsService: Failed to transfer NFT {nft_address}: {e}")
            return None

getgems_service = GetGemsService()
