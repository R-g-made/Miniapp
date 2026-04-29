from typing import Tuple, Optional
from uuid import UUID
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.sticker import UserSticker, ThermosMapping
from backend.models.sticker_action import StickerAction
from backend.models.transaction import Transaction
from backend.models.enums import Currency, TransactionType, TransactionStatus, StickerActionType, ExternalProviderType
from backend.crud.sticker import sticker as crud_sticker
from backend.crud.wallet import wallet_repository
from backend.services.user_service import user_service
from backend.services.refund_service import refund_service
from backend.services.thermos_service import thermos_service
from backend.core.config import settings
from backend.core.exceptions import EntityNotFound, InvalidOperation
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

class StickerService:
    async def sync_pool_with_external_sources(self, db: AsyncSession) -> dict:
        """
        Синхронизирует пул стикеров с Thermos API и кошельком TON.
        Добавляет новые стикеры, если они появились во внешних источниках.
        """
        logger.info("StickerService: Starting pool synchronization...")
        results = {"thermos_added": 0, "onchain_added": 0, "archived": 0, "errors": []}
        
        # Флаги успешности запросов к внешним API
        thermos_synced = False
        onchain_synced = False
        
        # Списки для отслеживания того, что реально есть во внешних источниках
        seen_thermos_identifiers = set() # set of (catalog_id, number)
        seen_onchain_addresses = set()    # set of nft_address

        # 1. Синхронизация с Thermos
        try:
            thermos_stickers = await thermos_service.get_my_stickers()
            # Важно: get_my_stickers теперь должен возвращать None при ошибке, а не []
            if thermos_stickers is not None:
                thermos_synced = True
                # ... (загрузка маппингов и каталога)
                from backend.models.sticker import ThermosMapping, StickerCatalog
                stmt_map = select(ThermosMapping)
                res_map = await db.execute(stmt_map)
                mapping_dict = {(m.thermos_collection_id, m.thermos_character_id): m.catalog_id for m in res_map.scalars().all()}
                
                stmt_cat = select(StickerCatalog)
                res_cat = await db.execute(stmt_cat)
                catalog_items = {c.id: c for c in res_cat.scalars().all()}

                for ts in thermos_stickers:
                    coll_id, char_id, instance = ts.get("collection_id"), ts.get("character_id"), ts.get("instance")
                    if coll_id is None or char_id is None or instance is None: continue
                    
                    catalog_id = mapping_dict.get((coll_id, char_id))
                    if not catalog_id or catalog_id not in catalog_items: continue
                    
                    # Помечаем как увиденный
                    seen_thermos_identifiers.add((catalog_id, instance))
                    
                    # Проверка на существование в БД
                    stmt_exists = select(UserSticker).where(UserSticker.catalog_id == catalog_id, UserSticker.number == instance)
                    existing = (await db.execute(stmt_exists)).scalar_one_or_none()
                    
                    if existing:
                        if existing.owner_id is None and not existing.is_available:
                            existing.is_available = True
                            existing.is_onchain = False
                            existing.unlock_date = None
                            results["thermos_added"] += 1
                        continue

                    catalog = catalog_items[catalog_id]
                    db.add(UserSticker(
                        catalog_id=catalog_id,
                        number=instance,
                        is_available=True,
                        is_onchain=False,
                        ton_price=catalog.floor_price_ton,
                        stars_price=catalog.floor_price_stars,
                        nft_address=ts.get("nft_address") or ts.get("address"),
                        owner_id=None
                    ))
                    results["thermos_added"] += 1
        except Exception as e:
            logger.error(f"StickerService: Thermos sync failed: {e}")
            results["errors"].append(f"Thermos: {str(e)}")

        # 2. Синхронизация с Blockchain (On-chain)
        try:
            merchant_address = settings.MERCHANT_TON_ADDRESS
            if merchant_address:
                import httpx
                from ton_core import Address
                base_url = "https://testnet.tonapi.io/v2" if settings.IS_TESTNET else "https://tonapi.io/v2"
                headers = {"Authorization": f"Bearer {settings.TON_API_KEY}"} if settings.TON_API_KEY else {}
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(f"{base_url}/accounts/{merchant_address}/nfts", headers=headers)
                    if resp.status_code == 200:
                        nfts = resp.json().get("nft_items", [])
                        onchain_synced = True
                    else:
                        nfts = []

                if onchain_synced:
                    # ... (загрузка каталога)
                    stmt_cat = select(StickerCatalog).where(StickerCatalog.collection_address != None)
                    catalog_items_onchain = (await db.execute(stmt_cat)).scalars().all()
                    catalog_map = {}
                    for c in catalog_items_onchain:
                        try: catalog_map[Address(c.collection_address).to_str(is_user_friendly=False)] = c
                        except: continue

                    for nft in nfts:
                        nft_addr = nft.get("address")
                        coll_addr = nft.get("collection", {}).get("address")
                        if not nft_addr or not coll_addr: continue
                        
                        try: norm_coll_addr = Address(coll_addr).to_str(is_user_friendly=False)
                        except: continue
                        
                        catalog = catalog_map.get(norm_coll_addr)
                        if not catalog: continue

                        # Помечаем как увиденный
                        seen_onchain_addresses.add(nft_addr)

                        stmt_exists = select(UserSticker).where(UserSticker.nft_address == nft_addr)
                        existing = (await db.execute(stmt_exists)).scalar_one_or_none()
                        
                        if existing:
                            if existing.owner_id is None and not existing.is_available:
                                existing.is_available = True
                                existing.is_onchain = True
                                existing.unlock_date = None
                                results["onchain_added"] += 1
                            continue

                        import re
                        match = re.search(r'#(\d+)', nft.get("metadata", {}).get("name", ""))
                        number = int(match.group(1)) if match else 0

                        db.add(UserSticker(
                            catalog_id=catalog.id,
                            number=number,
                            is_available=True,
                            is_onchain=True,
                            nft_address=nft_addr,
                            ton_price=catalog.floor_price_ton,
                            stars_price=catalog.floor_price_stars,
                            owner_id=None
                        ))
                        results["onchain_added"] += 1
        except Exception as e:
            logger.error(f"StickerService: On-chain sync failed: {e}")
            results["errors"].append(f"On-chain: {str(e)}")

        # 3. Безопасная архивация исчезнувших стикеров
        # Только если синхронизация с соответствующим источником прошла успешно!
        if thermos_synced or onchain_synced:
            stmt_pool = select(UserSticker).where(UserSticker.owner_id == None, UserSticker.is_available == True)
            pool_items = (await db.execute(stmt_pool)).scalars().all()
            
            for item in pool_items:
                should_archive = False
                
                if item.is_onchain and onchain_synced:
                    # Если ончейн синхронизирован, а этого стикера нет на кошельке - в архив
                    if item.nft_address not in seen_onchain_addresses:
                        should_archive = True
                elif not item.is_onchain and thermos_synced:
                    # Если оффчейн синхронизирован, а этого стикера нет в списке - в архив
                    if (item.catalog_id, item.number) not in seen_thermos_identifiers:
                        should_archive = True
                
                if should_archive:
                    item.is_available = False
                    results["archived"] += 1
                    logger.warning(f"StickerService: Archiving missing sticker {item.catalog_id} #{item.number}")

        await db.commit()
        logger.success(f"StickerService: Sync finished. Added/Reactivated: {results['thermos_added'] + results['onchain_added']}, Archived: {results['archived']}")
        return results

    async def process_sticker_unlocks(self, db: AsyncSession) -> int:
        """
        Снимает блокировку со стикеров, у которых истек срок (21 день).
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        stmt = (
            update(UserSticker)
            .where(
                UserSticker.unlock_date.isnot(None),
                UserSticker.unlock_date <= now
            )
            .values(unlock_date=None)
        )
        
        result = await db.execute(stmt)
        await db.commit()
        
        count = result.rowcount
        if count > 0:
            logger.info(f"StickerService: Unlocked {count} stickers.")
        return count

    async def transfer(
        self,
        db: AsyncSession,
        sticker_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Перевод NFT (on-chain или off-chain через Thermos).
        """
        
        if await refund_service.is_user_refunded(db, user_id):
            raise InvalidOperation("Your account is restricted due to payment refunds")

        # 1. Получаем стикер и владельца (с подгрузкой пользователя для telegram_id)
        from backend.models.user import User
        stmt = (
            select(UserSticker)
            .options(selectinload(UserSticker.owner), selectinload(UserSticker.catalog))
            .where(UserSticker.id == sticker_id)
        )
        result = await db.execute(stmt)
        sticker = result.scalar_one_or_none()
        
        if not sticker:
            raise EntityNotFound("Sticker not found")
        if sticker.owner_id != user_id:
            raise InvalidOperation("Not your sticker")
        
        user_telegram_id = sticker.owner.telegram_id
            
        # 2. Проверка кошелька (только если это On-chain)
        target_address = None
        if sticker.is_onchain:
            wallet = await wallet_repository.get_active_by_owner_id(db, owner_id=user_id)
            
            if not wallet:
                raise InvalidOperation("No active wallet connected. Please connect TON wallet first.")
            target_address = wallet.address
        
        # 3. Проверяем блокировку
        now = datetime.now(timezone.utc)
        # Убеждаемся, что обе даты имеют таймзону для сравнения
        sticker_unlock = sticker.unlock_date
        if sticker_unlock and sticker_unlock.tzinfo is None:
            sticker_unlock = sticker_unlock.replace(tzinfo=timezone.utc)
            
        is_locked = sticker_unlock and sticker_unlock > now
        if is_locked:
            raise InvalidOperation(f"Sticker is locked until {sticker.unlock_date}")

        # 4. Обработка трансфера
        try:
            if sticker.is_onchain:
                # 4a. On-chain NFT через ExternalApiService (GetGems/TonAPI)
                if not sticker.nft_address:
                    raise InvalidOperation("This on-chain sticker has no NFT address")

                from backend.schemas.external_api import StickerTransferRequest
                from backend.services.external_api_service import external_api_service
                
                # Для всех ончейн NFT используем GetGems/TonAPI провайдер
                provider = ExternalProviderType.GETGEMS

                transfer_res = await external_api_service.transfer_sticker(
                    StickerTransferRequest(
                        sticker_id=sticker.id,
                        target_address=target_address,
                        details={
                            "nft_address": sticker.nft_address,
                            "price_ton": sticker.catalog.floor_price_ton,
                            "is_onchain": True
                        }
                    ),
                    provider=provider
                )
                
                if not transfer_res.success:
                    raise InvalidOperation(f"On-chain transfer failed: {transfer_res.error}")
                
                tx_hash = transfer_res.details.get("tx_hash")
            else:
                # 4b. Off-chain (Всегда через Thermos API как Gift)
                # Ищем маппинг ID для Thermos
                mapping_stmt = select(ThermosMapping).where(ThermosMapping.catalog_id == sticker.catalog_id)
                mapping_res = await db.execute(mapping_stmt)
                mapping = mapping_res.scalar_one_or_none()
                
                if not mapping:
                    logger.error(f"StickerService: No Thermos mapping found for catalog {sticker.catalog_id}")
                    raise InvalidOperation("Sticker catalog is not mapped to Thermos API")

                payload = {
                    "owned_stickers": [
                        {
                            "collection_id": mapping.thermos_collection_id,
                            "character_id": mapping.thermos_character_id,
                            "instance": sticker.number,
                            "collection_name": mapping.thermos_collection_name,
                            "character_name": mapping.thermos_character_name
                        }
                    ],
                    "withdraw": False, # Перевод внутри Thermos (Gifts) по TG ID
                    "target_telegram_user_id": user_telegram_id, 
                    "wallet_address": None,
                    "anonymous": False
                }
                
                transfer_res = await thermos_service.transfer_sticker(payload)
                tx_hash = transfer_res.get("hash") or transfer_res.get("task_id")

            # 5. Обновляем состояние в БД после успешного трансфера
            sticker.owner_id = None # Стикер ушел из владения системы/пользователя
            sticker.is_available = False
            
            # Создаем запись о действии (WITHDRAW)
            action = StickerAction(
                sticker_pool_id=sticker.id,
                user_id=user_id,
                action_type=StickerActionType.WITHDRAW,
                hash=tx_hash
            )
            
            # Создаем транзакцию вывода
            transaction = Transaction(
                user_id=user_id,
                amount=0,
                currency=Currency.NFT if sticker.is_onchain else Currency.STARS, 
                type=TransactionType.TRANSFER_OUT,
                status=TransactionStatus.COMPLETED,
                details={
                    "target_address": target_address, 
                    "tx_hash": tx_hash,
                    "is_onchain": sticker.is_onchain
                }
            )
            
            db.add(sticker)
            db.add(action)
            db.add(transaction)
            await db.commit()
            
            # WS notification for sticker withdrawal
            from backend.core.websocket_manager import manager
            from backend.schemas.websocket import WSEventMessage
            from backend.models.enums import WSMessageType
            await manager.send_to_user(
                user_id=str(user_id),
                message=WSEventMessage(
                    type=WSMessageType.USER_EVENT,
                    event_type="sticker_withdrawn",
                    data={
                        "sticker_id": str(sticker_id),
                        "status": "success"
                    }
                )
            )
            
            logger.info(f"StickerService: Sticker {sticker_id} successfully withdrawn to {target_address}")
            return True
            
        except Exception as e:
            logger.error(f"StickerService: Withdrawal failed for {sticker_id}: {e}")
            if isinstance(e, InvalidOperation):
                raise
            raise InvalidOperation(f"Withdrawal failed: {str(e)}")

    async def auto_buy_stickers(self, db: AsyncSession):
        """Авто-покупка стикеров для пополнения пула"""
        logger.info("StickerService: Auto-buy is currently DISABLED (under development).")
        return
        
        from backend.services.external_api_service import external_api_service
        from backend.schemas.external_api import StickerPurchaseRequest, ExternalProviderType
        from backend.models.sticker import UserSticker, LaffkaMapping

        # 1. Получаем все каталоги
        catalogs = await crud_sticker.get_all_catalogs(db)
        
        for catalog in catalogs:
            # 2. Проверяем остаток в пуле
            count = await crud_sticker.count_available_in_pool(db, catalog.id)
            if count < 5: # Если в пуле меньше 5 штук
                needed = 5 - count
                # 3. Определяем провайдера: GetGems для ончейн, Laffka для оффчейн
                # (Thermos теперь только для трансферов)
                provider = ExternalProviderType.GETGEMS if catalog.is_onchain else ExternalProviderType.LAFFKA
                
                details = {"collection_address": catalog.collection_address}
                
                # Если Laffka — ищем маппинг
                if provider == ExternalProviderType.LAFFKA:
                    mapping_stmt = select(LaffkaMapping).where(LaffkaMapping.catalog_id == catalog.id)
                    mapping_res = await db.execute(mapping_stmt)
                    mapping = mapping_res.scalar_one_or_none()
                    if mapping:
                        details["laffka_sticker_id"] = mapping.laffka_sticker_id
                    else:
                        logger.warning(f"StickerService: No Laffka mapping for {catalog.name}, skip.")
                        continue

                # 4. Запрашиваем покупку через внешний API
                from ton_core import to_nano
                purchase_price = (catalog.floor_price_ton * 1.1 if catalog.floor_price_ton else 1.0)
                purchase_price_nano = to_nano(purchase_price, 9)
                
                purchase_req = StickerPurchaseRequest(
                    catalog_id=catalog.id,
                    max_price=purchase_price,
                    max_price_nano=purchase_price_nano,
                    currency=Currency.TON,
                    details=details
                )
                
                results = await external_api_service.buy_stickers([purchase_req for _ in range(needed)], provider=provider)
                
                for res in results:
                    if res.success:
                        # 5. Добавляем купленный стикер в пул (Mock)
                        await crud_sticker.create(db, obj_in={
                            "catalog_id": catalog.id,
                            "owner_id": None,
                            "is_available": True,
                            "number": count + 1,
                            "nft_address": f"EQ_MOCKED_{uuid.uuid4().hex[:8]}"
                        })
                        count += 1
                        
                        # 6. Обновляем цену флора на цену покупки
                        await crud_sticker.update_catalog_floor_price(
                            db, 
                            catalog_id=catalog.id, 
                            ton_price=purchase_price,
                            stars_price=purchase_price / settings.STARS_TO_TON_RATE
                        )
        await db.commit()

    async def update_all_floor_prices(self, db: AsyncSession):
        """Обновление флор-прайсов для всех стикеров в каталоге"""
        from backend.services.external_api_service import external_api_service
        from backend.schemas.external_api import FloorPriceUpdate, ExternalProviderType

        # 1. Получаем все каталоги
        catalogs = await crud_sticker.get_all_catalogs(db)
        
        for catalog in catalogs:
            # 2. Определяем провайдера: GetGems для ончейн, Laffka для оффчейн
            # (Thermos теперь только для трансферов)
            provider = ExternalProviderType.GETGEMS if catalog.is_onchain else ExternalProviderType.LAFFKA
            
            # 3. Получаем актуальные цены (Mock)
            results = await external_api_service.update_floor_price(
                [FloorPriceUpdate(
                    catalog_id=catalog.id,
                    details={"collection_address": catalog.collection_address}
                )], 
                provider=provider
            )
            
            for res in results:
                if res.success:
                    # 4. Обновляем в БД
                    new_price = res.details["new_price"]
                    await crud_sticker.update_catalog_floor_price(
                        db, 
                        catalog_id=catalog.id, 
                        ton_price=new_price,
                        stars_price=new_price / settings.STARS_TO_TON_RATE
                    )
        await db.commit()

    async def sell_sticker(
        self,
        db: AsyncSession,
        sticker_id: UUID,
        user_id: UUID,
        currency: Currency
    ) -> Tuple[UserSticker, float, float, Currency]:
        """
        Бизнес-логика продажи стикера системе.
        """
        # 0. Проверка на рефаунды
        if await refund_service.is_user_refunded(db, user_id):
            raise InvalidOperation("Your account is restricted due to payment refunds")

        # 1. Получаем стикер со всеми связями через CRUD
        sticker = await crud_sticker.get_with_details(db, sticker_id)
        
        if not sticker:
            raise EntityNotFound("Sticker not found")
            
        # 2. Проверка владельца
        if sticker.owner_id != user_id:
            raise InvalidOperation("Sticker does not belong to user")
            
        # 3. Проверка блокировки
        now = datetime.now(timezone.utc)
        sticker_unlock = sticker.unlock_date
        if sticker_unlock and sticker_unlock.tzinfo is None:
            sticker_unlock = sticker_unlock.replace(tzinfo=timezone.utc)
            
        is_locked = sticker_unlock and sticker_unlock > now
        if is_locked:
            # Если заблокирован - продажа ТОЛЬКО за Stars
            currency = Currency.STARS
            
        # 4. Расчет цены
        fee_multiplier = 1.0 - settings.MARKET_FEE_PERCENTAGE
        
        # Поддержка как строк, так и Enum для гибкости (тесты шлют строки)
        currency_val = currency.value.lower() if hasattr(currency, 'value') else str(currency).lower()
        
        if currency_val == "ton":
            price = sticker.catalog.floor_price_ton
            final_currency = Currency.TON
        elif currency_val == "stars":
            price = sticker.catalog.floor_price_stars
            final_currency = Currency.STARS
        else:
            raise InvalidOperation(f"Unsupported currency: {currency}")
            
        if price is None:
             raise InvalidOperation(f"Price in {currency_val.upper()} not set for this sticker")
             
        amount = round(price * fee_multiplier, 9)
        
        # 5. Обновление баланса через UserService
        new_balance = user_service.update_balance(sticker.owner, amount, final_currency, operation="add")

        # 6. Возврат в пул
        sticker.owner_id = None
        sticker.is_available = True
        sticker.unlock_date = None # Сбрасываем дату блокировки
        
        # 7. Создание транзакции
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            currency=final_currency,
            type=TransactionType.SELL_STICKER,
            status=TransactionStatus.COMPLETED,
            details={"sticker_id": str(sticker_id), "catalog_id": str(sticker.catalog_id)}
        )
        
        # Создаем запись о действии (SELL_TO_SYSTEM)
        action = StickerAction(
            sticker_pool_id=sticker.id,
            user_id=user_id,
            action_type=StickerActionType.SELL_TO_SYSTEM
        )
        
        db.add(sticker)
        db.add(sticker.owner)
        db.add(transaction)
        db.add(action)
        
        # 8. Фиксация изменений
        await db.commit()
        
        # WS notification for balance update
        from backend.core.websocket_manager import manager
        from backend.schemas.websocket import WSEventMessage, WSMessageType
        await manager.send_to_user(
            user_id=str(user_id),
            message=WSEventMessage(
                type=WSMessageType.BALANCE_UPDATE,
                data={
                    "currency": final_currency.value,
                    "new_balance": float(new_balance)
                }
            )
        )
        
        return sticker, amount, new_balance, currency

    # _process_sale_transaction удален, так как логика переехала в user_service и выше

sticker_service = StickerService()