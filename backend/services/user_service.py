from typing import Tuple, Optional
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.user import User
from backend.models.enums import Currency
from backend.core.exceptions import InsufficientFunds, InvalidOperation

from backend.crud.user import user_repository

class UserService:
    """
    Сервис для работы с пользователями и их балансами.
    """
    
    async def get_locked(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """
        Получает пользователя с блокировкой строки (FOR UPDATE).
        """
        return await user_repository.get_locked(db, user_id)

    def update_balance(self, user: User, amount: float, currency: Currency, operation: str = "add") -> float:
        """
        Универсальный метод для обновления баланса.
        currency: Currency.TON или Currency.STARS
        operation: 'add' (начисление) или 'sub' (списание)
        """
        currency_val = currency.value.lower() if hasattr(currency, 'value') else str(currency).lower()
        attr_name = f"balance_{currency_val}"
        
        if not hasattr(user, attr_name):
            logger.error(f"UserService: Unsupported currency '{currency_val}' for user {user.telegram_id}")
            raise InvalidOperation(f"Unsupported currency: {currency}")
            
        current_balance = getattr(user, attr_name)
        logger.debug(f"UserService: Updating balance for {user.telegram_id}. {operation.upper()} {amount} {currency_val}. Current: {current_balance}")
        
        if operation == "add":
            new_balance = current_balance + amount
            # Убираем таймзону для TIMESTAMP WITHOUT TIME ZONE
            user.last_deposit_at = datetime.now(timezone.utc).replace(tzinfo=None)
        elif operation == "sub":
            if current_balance < amount:
                logger.warning(f"UserService: Insufficient funds for {user.telegram_id}. Needs {amount}, has {current_balance} {currency_val}")
                raise InsufficientFunds(currency=currency_val.upper())
            new_balance = current_balance - amount
        else:
            logger.error(f"UserService: Unknown operation '{operation}'")
            raise InvalidOperation(f"Unknown balance operation: {operation}")
            
        setattr(user, attr_name, round(new_balance, 9)) 
        logger.info(f"UserService: {user.telegram_id} balance updated: {current_balance} -> {new_balance} {currency_val}")
        return new_balance

    async def set_custom_referral_percentage(self, db: AsyncSession, user_id: str, percentage: float):
        """
        Устанавливает персональный реферальный процент для пользователя.
        """
        user = await db.get(User, user_id)
        if not user:
            logger.error(f"UserService: User {user_id} not found for setting custom ref percentage")
            return
            
        old_percentage = user.custom_ref_percentage
        user.custom_ref_percentage = percentage
        db.add(user)
        await db.commit()
        
        logger.info(f"UserService: Updated custom ref percentage for {user.telegram_id}: {old_percentage}% -> {percentage}%")

user_service = UserService()