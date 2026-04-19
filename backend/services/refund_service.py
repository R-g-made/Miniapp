from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from aiogram import Bot
from loguru import logger
from backend.models.transaction import Transaction
from backend.models.user import User
from backend.models.sticker import UserSticker
import asyncio
from datetime import datetime, timedelta, timezone
from backend.models.enums import Currency, TransactionStatus, WSMessageType, TransactionType
from backend.core.config import settings
from backend.core.websocket_manager import manager
from backend.schemas.websocket import WSEventMessage

class RefundService:
    async def check_refunds(self, db: AsyncSession, bot: Bot):
        """
        Проверяет транзакции Stars на наличие рефаундов через Telegram API.
        """
        logger.info("RefundService: Starting periodic check for Stars refunds...")
        
        lookback_date = datetime.now(timezone.utc) - timedelta(days=settings.REFUND_LOOKBACK_DAYS)
        
        query = select(Transaction).where(
            Transaction.currency == Currency.STARS,
            Transaction.type == TransactionType.DEPOSIT,
            Transaction.status == TransactionStatus.COMPLETED,
            Transaction.hash.isnot(None),
            Transaction.created_at >= lookback_date
        )
        result = await db.execute(query)
        transactions = result.scalars().all()
        
        if not transactions:
            logger.debug("RefundService: No active Stars transactions to check.")
            return

        try:
            star_transactions = await bot.get_star_transactions()
            refunded_charge_ids = {
                t.id for t in star_transactions.transactions 
                if t.refund_date is not None
            }
            logger.debug(f"RefundService: Fetched {len(star_transactions.transactions)} transactions from Telegram, {len(refunded_charge_ids)} are refunds.")
        except Exception as e:
            logger.error(f"RefundService: Failed to fetch star transactions from Telegram: {e}")
            return

        refund_count = 0
        for tx in transactions:
            if tx.hash in refunded_charge_ids:
                logger.warning(f"RefundService: Refund detected for transaction {tx.hash}, user_id: {tx.user_id}")
                await self.process_refund(db, tx.user_id, tx)
                refund_count += 1
        
        if refund_count > 0:
            logger.info(f"RefundService: Processed {refund_count} refunds in this cycle.")
        else:
            logger.debug("RefundService: No new refunds detected.")

    async def process_refund(self, db: AsyncSession, user_id, transaction: Transaction):
        """
        Аннулирует баланс и стикеры пользователя при обнаружении рефаунда.
        """
        logger.info(f"RefundService: Processing refund for user {user_id} due to tx {transaction.hash}")
        
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(balance_ton=0.0, balance_stars=0.0)
        )
        
        await db.execute(
            update(UserSticker)
            .where(UserSticker.owner_id == user_id)
            .values(owner_id=None, is_available=True, unlock_date=None)
        )
        
        transaction.status = TransactionStatus.REFUNDED
        transaction.details = {**(transaction.details or {}), "refund_processed_at": str(datetime.now())}
        db.add(transaction)
        
        await db.commit()
        
        await manager.send_to_user(
            user_id=str(user_id),
            message=WSEventMessage(
                type=WSMessageType.BALANCE_UPDATE,
                data={
                    "message": "Your account has been reset due to a payment refund.",
                    "balance_ton": 0,
                    "balance_stars": 0,
                    "is_blocked": True
                }
            )
        )
        logger.success(f"RefundService: User {user_id} account fully reset and notified.")

    async def is_user_refunded(self, db: AsyncSession, user_id) -> bool:
        """
        Проверяет, есть ли у пользователя отозванные транзакции (для блокировки действий).
        """
        query = select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.status == TransactionStatus.REFUNDED
        )
        result = await db.execute(query)
        is_refunded = result.scalars().first() is not None
        if is_refunded:
            logger.warning(f"RefundService: Access denied for user {user_id} due to past refunds.")
        return is_refunded

refund_service = RefundService()