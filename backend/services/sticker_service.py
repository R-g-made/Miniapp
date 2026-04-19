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
from sqlalchemy import select

from ton_core import to_nano

class StickerService:
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

        # 1. Получаем стикер и владельца
        sticker = await crud_sticker.get_with_details(db, sticker_id)
        if not sticker:
            raise EntityNotFound("Sticker not found")
        if sticker.owner_id != user_id:
            raise InvalidOperation("Not your sticker")
            
        # 2. Проверяем, привязан ли кошелек у пользователя
        wallet = await wallet_repository.get_active_by_owner_id(db, owner_id=user_id)
        if not wallet:
            raise InvalidOperation("No wallet connected. Please connect TON wallet first.")
        
        target_address = wallet.address # Берем активный кошелек
        
        # 3. Проверяем блокировку
        is_locked = sticker.unlock_date and sticker.unlock_date > datetime.now(timezone.utc)
        if is_locked:
            raise InvalidOperation(f"Sticker is locked until {sticker.unlock_date}")

        # 4. Обработка трансфера (On-chain или Off-chain)
        try:
            # Теперь смотрим на статус конкретного экземпляра (is_onchain)
            if sticker.is_onchain:
                # 4a. On-chain NFT через ExternalApiService (GetGems/TonAPI)
                if not sticker.nft_address:
                    raise InvalidOperation("This on-chain sticker has no NFT address")

                from backend.schemas.external_api import StickerTransferRequest
                from backend.services.external_api_service import external_api_service
                
                # Используем приоритетный маркет из каталога или GetGems по умолчанию для ончейн
                provider_map = {
                    PriorityMarket.LAFFKA: ExternalProviderType.LAFFKA,
                    PriorityMarket.GETGEMS: ExternalProviderType.GETGEMS,
                    PriorityMarket.THERMOS: ExternalProviderType.THERMOS,
                }
                provider = provider_map.get(sticker.catalog.priority_market, ExternalProviderType.GETGEMS)
                
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
                # 4b. Off-chain (Laffka или Thermos)
                provider_map = {
                    PriorityMarket.LAFFKA: ExternalProviderType.LAFFKA,
                    PriorityMarket.THERMOS: ExternalProviderType.THERMOS,
                }
                provider = provider_map.get(sticker.catalog.priority_market, ExternalProviderType.LAFFKA)
                
                if provider == ExternalProviderType.LAFFKA:
                    # Вывод через Laffka (оффчейн стикерпак)
                    # nft_address в этом случае - это UUID стикера в системе Laffka
                    if not sticker.nft_address:
                        raise InvalidOperation("Laffka sticker UUID is missing")
                    
                    success = await laffka_service.withdraw_sticker(sticker.nft_address)
                    if not success:
                        raise InvalidOperation("Laffka off-chain withdrawal failed")
                    tx_hash = f"laffka_{sticker.nft_address}"
                else:
                    # Off-chain Gift через Thermos API
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
                        "withdraw": True, # Выводим на внешний кошелек
                        "target_telegram_user_id": None, # Не требуется при withdraw=True
                        "wallet_address": target_address,
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
        is_locked = sticker.unlock_date and sticker.unlock_date > datetime.now(timezone.utc)
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