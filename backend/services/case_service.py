from typing import Tuple, Optional
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
        
        # Сначала проверяем, что все ок и выбранный стикер есть в пуле!
        items = case_obj.items
        weights = [item.chance for item in items]
        selected_catalog_item: CaseItem = random.choices(items, weights=weights, k=1)[0]
        catalog_id = UUID(str(selected_catalog_item.sticker_catalog_id))
        logger.info(f"CaseService: Selected catalog item: {catalog_id}")
        
        won_sticker = await crud_sticker.get_random_from_pool(db, catalog_id)#Переделать логику сейчас ок,но при больших объмах будет медленее
        
        if not won_sticker:
            logger.error(f"CaseService: No available stickers in pool for catalog {catalog_id}")
            await self._handle_case_stock_change(db, case_obj.id)
            
            # # Сразу деактивируем кейс, если выбранный стикер закончился!
            # case_obj.is_active = False
            # db.add(case_obj)
            # await db.commit()
            
            # # WS broadcast for case deactivation
            # await manager.broadcast(WSEventMessage(
            #     type=WSMessageType.CASE_STATUS_UPDATE,
            #     data={
            #         "case_slug": case_slug,
            #         "is_active": False
            #     }
            # ))
            
            raise InvalidOperation(f"Case {case_slug} is temporarily unavailable (out of stock)")
        
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

        await live_drop_service.add_drop(
            image_url=won_sticker.catalog.image_url,
            floor_price_ton=won_sticker.catalog.floor_price_ton or 0.0
        )
        
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
            bonus_amount = amount * (referral_record.ref_percentage)
            
            logger.info(f"ReferralService: Awarding {bonus_amount} {currency.value} to referrer {referral_record.referrer_id} for purchase by {user.id}")
            
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
            count = await crud_sticker.count_available_in_pool(db, item.sticker_catalog_id)
            if count <= 0:
                has_empty_items = True
                empty_item_names.append(item.sticker_catalog.name)

        if has_empty_items:
            # Считаем общее количество доступных стикеров в кейсе
            total_available = 0
            for item in case_obj.items:
                total_available += await crud_sticker.count_available_in_pool(db, item.sticker_catalog_id)

            if case_obj.is_chance_distribution and total_available > 0:
                # Если включено распределение и есть хоть что-то — просто пересчитываем шансы
                logger.info(f"CaseService: Item(s) {empty_item_names} empty in case {case_obj.slug}. Redistributing chances.")
                await chance_service.recalculate_case_chances(db, case_obj.id)
            else:
                # Если распределение выключено ИЛИ вообще нет стикеров — отключаем кейс
                reason = "All items empty" if total_available <= 0 else f"Item(s) {empty_item_names} empty"
                logger.warning(f"CaseService: {reason} in case {case_obj.slug}. Deactivating case.")
                case_obj.is_active = False
                db.add(case_obj)
                
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

    async def check_inactive_cases(self, db: AsyncSession):
        """
        Периодическая проверка неактивных кейсов. 
        Если стикеры появились — включаем кейс обратно.
        """
        # Добавляем selectinload, чтобы избежать lazy loading ошибки
        stmt = select(Case).options(selectinload(Case.items)).where(Case.is_active == False)
        result = await db.execute(stmt)
        inactive_cases = result.scalars().all()
        
        for case_obj in inactive_cases:
            # Проверяем наличие стикеров
            available_items_count = 0
            all_items_available = True
            details = []
            
            for item in case_obj.items:
                count = await crud_sticker.count_available_in_pool(db, item.sticker_catalog_id)
                details.append(f"{item.sticker_catalog.name}: {count}")
                if count > 0:
                    available_items_count += 1
                else:
                    all_items_available = False
            
            logger.debug(f"CaseService: Checking case {case_obj.slug} (is_dist: {case_obj.is_chance_distribution}). Items: {', '.join(details)}")

            should_activate = False
            if case_obj.is_chance_distribution:
                # Если распределение включено, достаточно хотя бы одного айтема
                should_activate = available_items_count > 0
            else:
                # Если выключено, нужны ВСЕ айтемы
                should_activate = all_items_available and len(case_obj.items) > 0
            
            if should_activate:
                logger.info(f"CaseService: Reactivating case {case_obj.slug}. Distribution: {case_obj.is_chance_distribution}")
                case_obj.is_active = True
                
                # Если включено распределение, нужно пересчитать шансы при активации
                if case_obj.is_chance_distribution:
                    await chance_service.recalculate_case_chances(db, case_obj.id)
                
                db.add(case_obj)
                
                # Уведомляем админов
                await notification_service.notify_admins(f"✅ <b>Кейс восстановлен!</b>\nКейс: <code>{case_obj.name}</code> снова доступен.")
                
                # Сигнал по WS
                await manager.broadcast(WSEventMessage(
                    type=WSMessageType.CASE_STATUS_UPDATE,
                    data={"case_slug": case_obj.slug, "is_active": True}
                ))
        
        # Коммитим все изменения разом в конце
        await db.commit()

case_service = CaseService()