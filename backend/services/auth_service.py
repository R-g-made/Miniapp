from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status
from loguru import logger
import datetime
from backend.core.config import settings
from backend.core.security import security_service
from backend.crud.user import user_repository
from backend.models.user import User
from backend.core.exceptions import InvalidToken, InvalidOperation
from backend.services.referral_service import ReferralService
from backend.schemas.user import UserCreate

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.referral_service = ReferralService(db)

    async def authenticate_telegram_user(self, init_data: str) -> tuple[User, str]:
        '''Обработка InitData и создание рефферала'''
        # Парсинг данных (берем из init_data даже если подпись не валидна для тестов)
        user_data = security_service.parse_init_data(init_data)
        
        # В DEBUG режиме позволяем тестировать под разными ID без валидной подписи
        is_test_user = settings.DEBUG
        
        if not is_test_user:
            # Проверка подписи Telegram initData (в проде обязательна)
            if not security_service.verify_init_data_signature(init_data):
                logger.error(f"AuthService: Invalid initData signature for user_data: {user_data}")
                raise InvalidToken("Invalid initData signature")

        if not user_data or not user_data.get("id"):
            logger.warning(f"AuthService: Invalid initData format: {init_data[:50]}...")
            raise InvalidOperation("Invalid initData format")

        telegram_id = user_data.get("id")
        start_param = user_data.get("start_param") 
        
        user = await user_repository.get_by_telegram_id(self.db, telegram_id=telegram_id)
        
        user_in = UserCreate(
            telegram_id=telegram_id,
            username=user_data.get("username"),
            full_name=f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
            photo_url=user_data.get("photo_url"),
            language_code=user_data.get("language_code"),
            is_premium=user_data.get("is_premium", False),
            allows_write_to_pm=user_data.get("allows_write_to_pm", False)
        )

        if not user:
            logger.info(f"AuthService: Registering new user: {telegram_id} (@{user_data.get('username')})")
            user = await user_repository.create_user(
                self.db, 
                user_in=user_in
            )
            
            if start_param:
                logger.info(f"AuthService: Processing referral for user {telegram_id} with param: {start_param}")
                await self.referral_service.process_referral(user, start_param)
                    
        else:
            logger.debug(f"AuthService: Updating existing user: {telegram_id}")
            user = await user_repository.update(
                self.db, 
                db_obj=user, 
                obj_in=user_in
            )

        user.last_login_at = datetime.datetime.now()
        self.db.add(user)
        await self.db.flush()

        from sqlalchemy.orm import selectinload
        from sqlalchemy import select
        stmt = select(User).options(selectinload(User.wallets)).where(User.id == user.id)
        result = await self.db.execute(stmt)
        user = result.scalar_one()

        # Генерация токена
        access_token = security_service.create_access_token(subject=user.id)
        
        logger.info(f"AuthService: User authenticated successfully: {telegram_id} (Internal ID: {user.id})")
        
        return user, access_token