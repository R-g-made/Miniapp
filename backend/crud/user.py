from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.crud.base import BaseRepository
from backend.models.user import User

from backend.schemas.user import UserCreate

class UserRepository(BaseRepository[User]):
    async def get_by_telegram_id(self, db: AsyncSession, telegram_id: int) -> Optional[User]:
        query = select(self.model).where(self.model.telegram_id == telegram_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def create_user(
        self, 
        db: AsyncSession, 
        user_in: UserCreate
    ) -> User:
        """
        Создает нового пользователя.
        """
        user_data = user_in.model_dump()
        # Инициализируем баланс нулями
        user_data["balance_ton"] = 0.0
        user_data["balance_stars"] = 0.0
        
        return await self.create(db, obj_in=user_data)

user_repository = UserRepository(User)
