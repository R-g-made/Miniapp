from typing import Tuple, Optional, List
import random
from datetime import datetime, timedelta, timezone
from loguru import logger
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.models.user import User
from backend.models.enums import Currency, TransactionType, TransactionStatus, StickerActionType
from backend.models.case import Case
from backend.models.sticker import UserSticker, StickerCatalog
from backend.models.sticker_action import StickerAction
from backend.models.transaction import Transaction
from backend.models.associations import CaseItem
from backend.models.referral import Referral
from backend.crud.case import case as crud_case
from backend.crud.sticker import sticker as crud_sticker
from backend.services.user_service import user_service
from backend.services.live_drop_service import live_drop_service
from backend.services.chance_service import chance_service
from backend.services.notification_service import notification_service
from backend.core.websocket_manager import manager
from backend.schemas.websocket import WSEventMessage, WSMessageType
from backend.core.exceptions import EntityNotFound, InvalidOperation, InsufficientFunds
from backend.core.config import settings

class CaseService:
    async def open_case(
        self,
        db: AsyncSession,
        user: User,
        case_slug: str,
        currency: Currency = Currency.STARS
    ) -> Tuple[UserSticker, float, float]:
        """
        Открытие кейса пользователем.
        """
        logger.info(f"CaseService: Opening case '{case_slug}' for user {user.telegram_id} with currency {currency.value}")
        
        user = await user_service.get_locked(db, user.id)
        if not user:
             raise EntityNotFound("User not found")
        
        case_obj = await crud_case.get_by_slug(db, slug=case_slug)
        if not case_obj:
            logger.warning(f"CaseService: Case '{case_slug}' not found")
            raise EntityNotFound(f"Case with slug '{case_slug}' not found")
            
        if not case_obj.is_active:
            logger.warning(f"CaseService: Case '{case_slug}' is not active")
            raise InvalidOperation("Case is not active")
            
        if not case_obj.items:
            logger.warning(f"CaseService: Case '{case_slug}' has no items")
            raise InvalidOperation("Case is empty")

        price = case_obj.price_ton if currency == Currency.TON else case_obj.price_stars
        logger.info(f"CaseService: Case price: {price} {currency.value}")
        
        # Сначала проверяем наличие каждого айтема в пуле и формируем веса
        items = case_obj.items
        weights = []
        has_missing_items = False
        
        for item in items:
            cat_id_str = str(item.sticker_catalog_id)
            cat_id = UUID(cat_id_str)
            count = await crud_sticker.count_available_in_pool(db, cat_id)
            
            if count > 0:
                weights.append(item.chance)
            else:
                # Если стикер отключен, мы игнорируем его отсутствие (он не ломает кейс)
                if cat_id_str not in settings.DISABLED_STICKER_CATALOG_IDS:
                    has_missing_items = True
                
                # Шанс 0 для отсутствующего стикера
                weights.append(0.0)
        
        # ЖЕСТКАЯ ПРОВЕРКА: Если распределение выключено и чего-то не хватает — кейс не работает
        if not case_obj.is_chance_distribution and has_missing_items:
            logger.warning(f"CaseService: Case '{case_slug}' missing items with Dist: OFF. Deactivating.")
            await self._handle_case_stock_change(db, case_obj.id)
            raise InvalidOperation(f"Case {case_slug} is temporarily unavailable (out of stock)")

        if sum(weights) <= 0:
            logger.error(f"CaseService: No available stickers in pool for any item in case {case_slug}")
            await self._handle_case_stock_change(db, case_obj.id)
            raise InvalidOperation(f"Case {case_slug} is temporarily unavailable (out of stock)")

        # Временная функция: перевыбор, если выпал отключенный стикерпак
        max_rerolls = 10
        selected_catalog_item = None
        for _ in range(max_rerolls):
            selected = random.choices(items, weights=weights, k=1)[0]
            if str(selected.sticker_catalog_id) in settings.DISABLED_STICKER_CATALOG_IDS:
                logger.info(f"CaseService: Selected disabled catalog {selected.sticker_catalog_id}, rerolling...")
                continue
            selected_catalog_item = selected
            break
            
        # Если после 10 попыток всё равно ничего не выбрали (например, в кейсе остались ТОЛЬКО отключенные)
        if not selected_catalog_item:
            logger.error(f"CaseService: Only disabled stickers are dropping for case {case_slug}")
            raise InvalidOperation("Case is temporarily unavailable (all available items are disabled)")

        catalog_id = UUID(str(selected_catalog_item.sticker_catalog_id))
        logger.info(f"CaseService: Selected catalog item: {catalog_id}")
        
        won_sticker = await crud_sticker.get_random_from_pool(db, catalog_id)
        
        if not won_sticker:
            # Сюда мы попадаем только в случае race condition (кто-то купил стикер между нашей проверкой и попыткой забрать)
            logger.error(f"CaseService: Race condition! No available stickers in pool for catalog {catalog_id} after check.")
            raise InvalidOperation(f"Case {case_slug} is temporarily unavailable (item just sold out)")
        
        # Только теперь, когда мы уверены, что стикер есть — списываем деньги!
        try:
            new_balance = user_service.update_balance(user, price, currency, operation="sub")
            logger.info(f"CaseService: New balance for {user.telegram_id}: {new_balance} {currency.value}")
        except InsufficientFunds as e:
            logger.warning(f"CaseService: Insufficient funds for user {user.telegram_id}: {e.message}")
            raise e

        won_sticker.owner_id = user.id
        won_sticker.is_available = False 
        
        if currency == Currency.STARS:
            won_sticker.unlock_date = (datetime.now(timezone.utc) + timedelta(days=21)).replace(tzinfo=None)
            logger.info(f"CaseService: Sticker {won_sticker.id} locked until {won_sticker.unlock_date} (STARS payment)")
        else:
            won_sticker.unlock_date = None
            
        db.add(won_sticker)
        await db.flush()
        logger.info(f"CaseService: Sticker {won_sticker.id} assigned to user {user.telegram_id}")

        sticker_action = StickerAction(
            sticker_pool_id=won_sticker.id,
            user_id=user.id,
            action_type=StickerActionType.DROP
        )
        db.add(sticker_action)

        await self._process_referral_reward(db, user, price, currency)
        
        transaction = Transaction(
            user_id=user.id,
            amount=price,
            currency=currency,
            type=TransactionType.OPEN_CASE,
            status=TransactionStatus.COMPLETED,
            details={"case_slug": case_slug, "won_sticker_id": str(won_sticker.id)}
        )
        db.add(transaction)

        #Статистика

        user.total_cases_opened += 1
        if currency == Currency.TON:
            user.total_spent_ton = round(user.total_spent_ton + price, 9)
        else:
            user.total_spent_stars = round(user.total_spent_stars + price, 9)
        
        db.add(user)
        
        await db.commit()
        
        # WS notification for balance update after case opening
        #Нужно ли
        # await manager.send_to_user(
        #     user_id=str(user.id),
        #     message=WSEventMessage(
        #         type=WSMessageType.BALANCE_UPDATE,
        #         data={
        #             "currency": currency.value,
        #             "new_balance": float(new_balance)
        #         }
        #     )
        # )
        
        logger.info(f"CaseService: Transaction and analytics updated for user {user.telegram_id}")
        
        # 7.5. Проверяем наличие стикеров и пересчитываем шансы или отключаем кейс
        await self._handle_case_stock_change(db, case_obj.id)
        
        stmt = select(UserSticker).options(
            selectinload(UserSticker.catalog).selectinload(StickerCatalog.issuer)
        ).where(UserSticker.id == won_sticker.id)
        result = await db.execute(stmt)
        won_sticker = result.scalar_one()

        # Отложенная отправка в Live Drop, чтобы не было спойлеров (5 секунд)
        import asyncio
        async def delayed_add_drop(image_url: str, price: float):
            await asyncio.sleep(5)
            await live_drop_service.add_drop(
                image_url=image_url,
                floor_price_ton=price
            )
            
        asyncio.create_task(delayed_add_drop(
            image_url=won_sticker.catalog.image_url,
            price=won_sticker.catalog.floor_price_ton or 0.0
        ))
        
        return won_sticker, price, new_balance

    async def _process_referral_reward(self, db: AsyncSession, user: User, amount: float, currency: Currency):
        """
        Начисление процента пригласителю в его реферальную статистику.
        Бонусы записываются в конкретную связь (Referral record).
        """
        stmt = select(Referral).where(Referral.referred_id == user.id)
        result = await db.execute(stmt)
        referral_record = result.scalar_one_or_none()
        
        if referral_record:
            # Награда рассчитывается от 10% стоимости кейса
            base_reward_amount = amount * 0.10
            bonus_amount = base_reward_amount * (referral_record.ref_percentage)
            
            logger.info(f"ReferralService: Awarding {bonus_amount} {currency.value} to referrer {referral_record.referrer_id} for purchase by {user.id} (Base: {base_reward_amount})")
            
            if currency == Currency.TON:
                referral_record.reward_ton += bonus_amount
            else:
                # Награды за Stars попадают в холдинг на 21 день
                referral_record.reward_stars_locked += bonus_amount
            
            referral_transaction = Transaction(
                user_id=referral_record.referrer_id,
                amount=bonus_amount,
                currency=currency,
                type=TransactionType.REFERRAL_REWARD,
                status=TransactionStatus.COMPLETED,
                details={
                    "from_user_id": str(user.id),
                    "referral_record_id": str(referral_record.id)
                }
            )
            
            db.add(referral_record)
            db.add(referral_transaction)
        else:
            logger.debug(f"ReferralService: No referrer found for user {user.id}")

    async def _handle_case_stock_change(self, db: AsyncSession, case_id: UUID):
        """
        Проверка остатков после открытия. 
        Если что-то закончилось: либо ребаланс шансов, либо деактивация кейса.
        """
        stmt = (
            select(Case)
            .options(selectinload(Case.items).selectinload(CaseItem.sticker_catalog))
            .where(Case.id == case_id)
        )
        result = await db.execute(stmt)
        case_obj = result.scalar_one_or_none()
        
        if not case_obj:
            return

        has_empty_items = False
        empty_item_names = []
        
        for item in case_obj.items:
            cat_id_str = str(item.sticker_catalog_id)
            # Игнорируем стикеры из списка отключенных (они не влияют на "пустоту" кейса)
            if cat_id_str in settings.DISABLED_STICKER_CATALOG_IDS:
                continue
                
            # Принудительно приводим к UUID для надежности сравнения
            cat_id = UUID(cat_id_str)
            count = await crud_sticker.count_available_in_pool(db, cat_id)
            if count <= 0:
                has_empty_items = True
                empty_item_names.append(item.sticker_catalog.name)
            else:
                logger.debug(f"CaseService: Item '{item.sticker_catalog.name}' has {count} stickers in pool")

        if has_empty_items:
            # Считаем общее количество доступных стикеров в кейсе (кроме отключенных)
            total_available = 0
            for item in case_obj.items:
                if str(item.sticker_catalog_id) not in settings.DISABLED_STICKER_CATALOG_IDS:
                    total_available += await crud_sticker.count_available_in_pool(db, UUID(str(item.sticker_catalog_id)))

            # ЖЕСТКАЯ ПРОВЕРКА:
            # Если distribution=True -> кейс живет пока есть хоть один стикер
            # Если distribution=False -> кейс умирает если нет хотя бы одного типа стикера
            if case_obj.is_chance_distribution and total_available > 0:
                logger.info(f"CaseService: Item(s) {empty_item_names} empty in case {case_obj.slug}. Redistributing chances.")
                await chance_service.recalculate_case_chances(db, case_obj.id)
            else:
                # Отключаем кейс
                reason = "All items empty" if total_available <= 0 else f"Item(s) {empty_item_names} empty (Dist: OFF)"
                logger.warning(f"CaseService: {reason} in case {case_obj.slug}. Deactivating case.")
                case_obj.is_active = False
                db.add(case_obj)
                
                # ВСЕГДА коммитим изменение статуса кейса
                await db.commit()
                
                # WS broadcast for case deactivation
                await manager.broadcast(WSEventMessage(
                    type=WSMessageType.CASE_STATUS_UPDATE,
                    data={
                        "case_slug": case_obj.slug,
                        "is_active": False
                    }
                ))
                
                # Уведомляем админов
                admin_msg = f"⚠️ <b>Кейс отключен!</b>\nКейс: <code>{case_obj.name}</code> ({case_obj.slug})\nПричина: {reason}"
                await notification_service.notify_admins(admin_msg)

    async def _try_reactivate_cases(self, db: AsyncSession, cases: List[Case]) -> None:
        """Попытка воскресить переданные выключенные кейсы"""
        for case_obj in cases:
            try:
                # Если кейс в списке навсегда отключенных, даже не пытаемся его включить
                if str(case_obj.id) in settings.DISABLED_CASE_IDS:
                    logger.debug(f"CaseService: Case '{case_obj.name}' is in DISABLED_CASE_IDS list. Skipping reactivation.")
                    continue

                available_types = []
                missing_types = []
                
                for item in case_obj.items:
                    cat_id_str = str(item.sticker_catalog_id)
                    # Игнорируем отключенные стикеры при проверке воскрешения
                    if cat_id_str in settings.DISABLED_STICKER_CATALOG_IDS:
                        continue
                        
                    cat_id = UUID(cat_id_str)
                    count = await crud_sticker.count_available_in_pool(db, cat_id)
                    if count > 0:
                        available_types.append(f"{item.sticker_catalog.name} ({count} шт.)")
                    else:
                        missing_types.append(item.sticker_catalog.name)
                
                # Логика активации
                # Считаем количество активных элементов в кейсе (исключая отключенные)
                active_items_count = len([i for i in case_obj.items if str(i.sticker_catalog_id) not in settings.DISABLED_STICKER_CATALOG_IDS])
                
                if case_obj.is_chance_distribution:
                    should_activate = len(available_types) > 0
                    condition_msg = "Dist: ON"
                else:
                    should_activate = len(missing_types) == 0 and active_items_count > 0
                    condition_msg = "Dist: OFF"

                if should_activate:
                    logger.success(f"CaseService: RE-ACTIVATING case '{case_obj.name}' ({case_obj.slug})")
                    case_obj.is_active = True
                    
                    if case_obj.is_chance_distribution:
                        from backend.services.chance_service import chance_service
                        await chance_service.recalculate_case_chances(db, case_obj.id)
                    
                    db.add(case_obj)
                    
                    await notification_service.notify_admins(f"✅ <b>Кейс восстановлен!</b>\nКейс: <code>{case_obj.name}</code> снова доступен.")
                    await manager.broadcast(WSEventMessage(
                        type=WSMessageType.CASE_STATUS_UPDATE,
                        data={"case_slug": case_obj.slug, "is_active": True}
                    ))
            except Exception as e:
                logger.error(f"CaseService: Error processing case {case_obj.slug}: {e}")

    async def check_inactive_cases(self, db: AsyncSession):
        """
        Периодическая проверка неактивных кейсов. 
        """
        try:
            # Загружаем неактивные кейсы со всеми связями
            stmt = (
                select(Case)
                .options(
                    selectinload(Case.items).selectinload(CaseItem.sticker_catalog)
                )
                .where(Case.is_active == False)
            )
            result = await db.execute(stmt)
            inactive_cases = result.scalars().all()
            
            if not inactive_cases:
                return

            await self._try_reactivate_cases(db, inactive_cases)
            
            await db.commit()
        except Exception as e:
            logger.error(f"CaseService: check_inactive_cases global error: {e}")
            await db.rollback()

case_service = CaseService()