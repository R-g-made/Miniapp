from typing import Tuple, Optional
from uuid import UUID
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.sticker import UserSticker, ThermosMapping, StickerCatalog
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
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

class StickerService:
    async def sync_pool_with_external_sources(self, db: AsyncSession) -> dict:
        """
        Синхронизирует пул стикеров с Thermos API и кошельком TON.
        Добавляет новые стикеры, если они появились во внешних источниках.
        """
        logger.info("StickerService: Starting pool synchronization...")
        
        # --- УДАЛЕНИЕ СУЩЕСТВУЮЩИХ ДУБЛИКАТОВ ИЗ БД ---
        try:
            stmt = select(UserSticker)
            res = await db.execute(stmt)
            all_stickers = res.scalars().all()
            
            from collections import defaultdict
            grouped = defaultdict(list)
            for s in all_stickers:
                grouped[(str(s.catalog_id), s.number)].append(s)
                
            deleted_dups = 0
            for key, group in grouped.items():
                if len(group) > 1:
                    # Сортируем: сначала те, у которых есть владелец, затем доступные
                    group.sort(key=lambda x: (0 if x.owner_id is not None else 1, 0 if x.is_available else 1))
                    # Оставляем первый (самый приоритетный), остальные удаляем полностью
                    for s in group[1:]:
                        # Сначала удаляем связанные действия (историю)
                        from backend.models.sticker_action import StickerAction
                        await db.execute(StickerAction.__table__.delete().where(StickerAction.sticker_pool_id == s.id))
                        # Затем удаляем сам стикер
                        await db.delete(s)
                        deleted_dups += 1
            if deleted_dups > 0:
                await db.commit()
                logger.info(f"StickerService: Hard deleted {deleted_dups} duplicate stickers from DB.")
        except Exception as e:
            logger.error(f"StickerService: Duplicate hard cleanup failed: {e}")
        # --- КОНЕЦ УДАЛЕНИЯ ДУБЛИКАТОВ ---

        results = {"thermos_added": 0, "onchain_added": 0, "archived": 0, "errors": []}
        
        # Флаги успешности запросов к внешним API
        thermos_synced = False
        onchain_synced = False
        
        # Списки для отслеживания того, что реально есть во внешних источниках
        # Используем кортежи (str, int) для Thermos и строки для On-chain
        seen_thermos_identifiers = set() 
        seen_onchain_addresses = set()    

        # 1. Синхронизация с Thermos
        try:
            thermos_stickers = await thermos_service.get_my_stickers()
            if thermos_stickers is not None:
                thermos_synced = True
                
                # Загружаем маппинги и каталог
                stmt_map = select(ThermosMapping)
                res_map = await db.execute(stmt_map)
                mappings = res_map.scalars().all()
                
                # Ключ - (coll_id, char_id), Значение - список catalog_id (UUID)
                # Это важно, если один стикер в Thermos соответствует нескольким записям в нашем каталоге
                mapping_dict = {}
                all_mapped_catalog_ids = set()
                for m in mappings:
                    key = (m.thermos_collection_id, m.thermos_character_id)
                    if key not in mapping_dict:
                        mapping_dict[key] = []
                    mapping_dict[key].append(m.catalog_id)
                    all_mapped_catalog_ids.add(str(m.catalog_id))
                
                stmt_cat = select(StickerCatalog)
                res_cat = await db.execute(stmt_cat)
                catalog_items = {c.id: c for c in res_cat.scalars().all()}

                # 1. Сначала соберем все пары (catalog_id, instance) из Thermos
                thermos_to_sync = []
                for ts in thermos_stickers:
                    try:
                        coll_id = int(ts.get("collection_id"))
                        char_id = int(ts.get("character_id"))
                        instance = int(ts.get("instance"))
                    except (TypeError, ValueError):
                        continue
                        
                    catalog_ids = mapping_dict.get((coll_id, char_id)) or []
                    if not catalog_ids:
                        logger.warning(f"StickerService: Found sticker in Thermos ({coll_id}:{char_id}) but NO mapping exists in DB!")
                        continue
                    
                    for catalog_id in catalog_ids:
                        if catalog_id in catalog_items:
                            thermos_to_sync.append({
                                "catalog_id": catalog_id,
                                "instance": instance,
                                "nft_address": ts.get("nft_address") or ts.get("address")
                            })

                # 2. Получим все существующие стикеры для этих каталогов одним запросом
                if thermos_to_sync:
                    target_catalog_ids = list(set(s["catalog_id"] for s in thermos_to_sync))
                    stmt_existing = select(UserSticker).where(UserSticker.catalog_id.in_(target_catalog_ids))
                    res_existing = await db.execute(stmt_existing)
                    # Кэшируем существующие в словарь для быстрого поиска: (catalog_id_str, number) -> sticker
                    existing_map = {(str(s.catalog_id), s.number): s for s in res_existing.scalars().all()}

                    for item in thermos_to_sync:
                        cat_id = item["catalog_id"]
                        cat_id_str = str(cat_id)
                        inst = item["instance"]
                        
                        # Защита от создания дубликатов в одном цикле
                        if (cat_id_str, inst) in seen_thermos_identifiers:
                            continue
                            
                        # Помечаем как увиденный
                        seen_thermos_identifiers.add((cat_id_str, inst))
                        
                        existing = existing_map.get((cat_id_str, inst))
                        
                        if existing:
                            if not existing.is_available:
                                logger.info(f"StickerService: Reactivating archived thermos sticker {cat_id} #{inst}")
                                existing.is_available = True
                                existing.owner_id = None
                                existing.unlock_date = None
                                results["thermos_added"] += 1
                            elif existing.owner_id is not None:
                                logger.warning(f"StickerService: Sticker {cat_id} #{inst} is in Thermos pool but owned by {existing.owner_id}")
                            continue

                        # Если не нашли — создаем
                        catalog = catalog_items[cat_id]
                        db.add(UserSticker(
                            catalog_id=cat_id,
                            number=inst,
                            is_available=True,
                            is_onchain=False,
                            ton_price=catalog.floor_price_ton,
                            stars_price=catalog.floor_price_stars,
                            nft_address=item["nft_address"],
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
                
                nfts = []
                offset, limit = 0, 100
                async with httpx.AsyncClient(timeout=30.0) as client:
                    while True:
                        resp = await client.get(
                            f"{base_url}/accounts/{merchant_address}/nfts", 
                            params={"limit": limit, "offset": offset},
                            headers=headers
                        )
                        if resp.status_code != 200: break
                        items = resp.json().get("nft_items", [])
                        nfts.extend(items)
                        if len(items) < limit:
                            onchain_synced = True
                            break
                        offset += limit

                if onchain_synced:
                    stmt_cat = select(StickerCatalog)
                    all_catalogs = (await db.execute(stmt_cat)).scalars().all()
                    
                    from ton_core import Address
                    from backend.services.floor_price_service import floor_price_service
                    
                    # 1. Строим маппинг по адресу коллекции
                    catalog_map_by_address = {}
                    for c in all_catalogs:
                        if c.collection_address:
                            try: 
                                norm_addr = Address(c.collection_address).to_str(is_user_friendly=False)
                                catalog_map_by_address[norm_addr] = c
                            except: continue

                    # 2. Строим маппинг по нормализованному имени коллекции (для случаев без адреса)
                    catalog_map_by_name = {}
                    for c in all_catalogs:
                        norm_cname = floor_price_service._normalize_name(c.collection_name or "")
                        if norm_cname:
                            catalog_map_by_name[norm_cname] = c

                    for nft in nfts:
                        try:
                            nft_addr = Address(nft.get("address")).to_str(is_user_friendly=False)
                            coll_data = nft.get("collection") or {}
                            coll_addr = Address(coll_data.get("address")).to_str(is_user_friendly=False) if coll_data.get("address") else None
                            coll_name = coll_data.get("name") or ""
                        except: continue
                        
                        # Пытаемся найти каталог сначала по адресу, затем по имени
                        catalog = None
                        if coll_addr:
                            catalog = catalog_map_by_address.get(coll_addr)
                        
                        if not catalog and coll_name:
                            norm_coll_name = floor_price_service._normalize_name(coll_name)
                            catalog = catalog_map_by_name.get(norm_coll_name)

                        if not catalog: continue

                        # Защита от создания дубликатов в одном цикле
                        if nft_addr in seen_onchain_addresses:
                            continue

                        seen_onchain_addresses.add(nft_addr)
                        stmt_exists = (
                            select(UserSticker)
                            .where(UserSticker.nft_address == nft_addr)
                            .limit(1)
                        )
                        existing = (await db.execute(stmt_exists)).scalars().first()
                        
                        if existing:
                            if not existing.is_available:
                                logger.info(f"StickerService: Reactivating archived onchain sticker {nft_addr}")
                                existing.is_available = True
                                existing.owner_id = None
                                existing.unlock_date = None
                                results["onchain_added"] += 1
                            continue

                        import re
                        match = re.search(r'#(\d+)', nft.get("metadata", {}).get("name", ""))
                        number = int(match.group(1)) if match else 0

                        db.add(UserSticker(
                            catalog_id=catalog.id, number=number, is_available=True, is_onchain=True,
                            nft_address=nft_addr, ton_price=catalog.floor_price_ton,
                            stars_price=catalog.floor_price_stars, owner_id=None
                        ))
                        results["onchain_added"] += 1
        except Exception as e:
            logger.error(f"StickerService: On-chain sync failed: {e}")
            results["errors"].append(f"On-chain: {str(e)}")

        # 3. Безопасная архивация
        if thermos_synced or onchain_synced:
            stmt_pool = select(UserSticker).where(UserSticker.owner_id == None, UserSticker.is_available == True)
            pool_items = (await db.execute(stmt_pool)).scalars().all()
            from ton_core import Address
            
            # Трекинг для очистки уже существующих дубликатов в БД
            processed_onchain_in_pool = set()
            processed_thermos_in_pool = set()
            
            for item in pool_items:
                should_archive = False
                
                # Архивация On-chain стикеров
                if item.is_onchain and onchain_synced:
                    if item.nft_address:
                        try:
                            # Нормализуем адрес перед сравнением
                            norm_addr = Address(item.nft_address).to_str(is_user_friendly=False)
                            if norm_addr not in seen_onchain_addresses:
                                should_archive = True
                                logger.warning(f"StickerService: Archiving onchain sticker {item.nft_address} - not found on wallet")
                            elif norm_addr in processed_onchain_in_pool:
                                # Это дубликат в пуле! Архивируем его
                                should_archive = True
                                logger.warning(f"StickerService: Archiving duplicate onchain sticker {item.nft_address}")
                            else:
                                processed_onchain_in_pool.add(norm_addr)
                        except Exception as e:
                            logger.error(f"StickerService: Error normalizing address {item.nft_address}: {e}")
                    else:
                        should_archive = True
                        
                # Архивация Thermos стикеров
                elif not item.is_onchain and thermos_synced:
                    # Архивация ТОЛЬКО если для этого каталога существует маппинг в Thermos
                    # Если маппинга нет, мы не можем доверять результатам синхронизации Thermos для этого стикера
                    if str(item.catalog_id) in all_mapped_catalog_ids:
                        key = (str(item.catalog_id), item.number)
                        if key not in seen_thermos_identifiers:
                            should_archive = True
                            logger.warning(f"StickerService: Archiving missing thermos sticker {item.catalog_id} #{item.number} - not found in API")
                        elif key in processed_thermos_in_pool:
                            # Это дубликат в пуле! Архивируем его
                            should_archive = True
                            logger.warning(f"StickerService: Archiving duplicate thermos sticker {item.catalog_id} #{item.number}")
                        else:
                            processed_thermos_in_pool.add(key)
                
                if should_archive:
                    item.is_available = False
                    results["archived"] += 1

        await db.commit()
        
        # 4. Восстановление кейсов
        # Если были добавлены или реактивированы стикеры, проверяем, не нужно ли включить кейсы
        if results["thermos_added"] > 0 or results["onchain_added"] > 0:
            from backend.services.case_service import case_service
            try:
                await case_service.check_inactive_cases(db)
                logger.info("StickerService: Case reactivation check completed after sync")
            except Exception as e:
                logger.error(f"StickerService: Failed to reactivate cases: {e}")

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
        
        # 9. Синхронизация кейсов после продажи стикера
        try:
            from backend.services.case_service import case_service
            from backend.services.chance_service import chance_service
            from backend.models.case import Case, CaseItem
            from sqlalchemy import select
            
            # Получаем ВСЕ кейсы (и активные, и неактивные), в которых есть этот проданный стикер
            stmt = select(Case).options(
                selectinload(Case.items).selectinload(CaseItem.sticker_catalog)
            ).join(CaseItem).where(
                CaseItem.sticker_catalog_id == sticker.catalog_id
            ).distinct()
            
            res = await db.execute(stmt)
            affected_cases = res.scalars().all()
            
            inactive_cases = []
            
            for c in affected_cases:
                # 1. Если кейс выключен - собираем в список для точечного воскрешения
                if not c.is_active:
                    inactive_cases.append(c)
                
                # 2. Если кейс активен и в нем включено распределение шансов - пересчитываем их
                elif c.is_active and c.is_chance_distribution:
                    await chance_service.recalculate_case_chances(db, c.id)
            
            # Воскрешаем ТОЛЬКО те кейсы, которые связаны с этим проданным стикером
            if inactive_cases:
                await case_service._try_reactivate_cases(db, inactive_cases)
                await db.commit() # Сохраняем воскрешения
                
            logger.info(f"StickerService: Successfully synced cases after selling sticker {sticker.catalog_id}")
        except Exception as e:
            logger.error(f"StickerService: Failed to sync cases after sale: {e}")
        
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