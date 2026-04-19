from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID
from backend.crud.base import BaseRepository
from backend.models.referral import Referral

class ReferralRepository(BaseRepository[Referral]):
    async def get_by_referred_id(self, db: AsyncSession, referred_id: UUID) -> Referral | None:
        """Получает реферальную запись по ID приглашенного"""
        query = select(Referral).where(Referral.referred_id == referred_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_stats(self, db: AsyncSession, user_id: UUID) -> dict:
        """
        Получает статистику реферальной программы для пользователя.
        """
        #Количество приглашенных
        count_query = select(func.count(Referral.id)).where(Referral.referrer_id == user_id)
        total_invited = await db.scalar(count_query) or 0
        
        #Заработанные TON
        ton_query = select(func.sum(Referral.reward_ton)).where(Referral.referrer_id == user_id)
        total_ton = await db.scalar(ton_query) or 0.0
        
        #Заработанные Stars (общая сумма locked + available)
        stars_query = select(
            func.sum(Referral.reward_stars_locked + Referral.reward_stars_available)
        ).where(Referral.referrer_id == user_id)
        total_stars = await db.scalar(stars_query) or 0.0

        # Заблокированные Stars (locked)
        stars_locked_query = select(func.sum(Referral.reward_stars_locked)).where(Referral.referrer_id == user_id)
        locked_stars = await db.scalar(stars_locked_query) or 0.0

        # Доступные Stars
        stars_available_query = select(func.sum(Referral.reward_stars_available)).where(Referral.referrer_id == user_id)
        available_stars = await db.scalar(stars_available_query) or 0.0
        
        return {
            "total_invited": total_invited,
            "total_ton": total_ton,
            "available_ton": total_ton, # Для TON у нас пока нет разделения на locked/available в модели
            "total_stars": total_stars,
            "locked_stars": locked_stars,
            "available_stars": available_stars
        }

    async def get_available_balance(self, db: AsyncSession, user_id: UUID, currency: str) -> float:
        """
        Возвращает доступную для вывода сумму реферальных вознаграждений.
        """
        if currency.upper() == "TON":
            attr = Referral.reward_ton
        else:
            attr = Referral.reward_stars_available
            
        query = select(func.sum(attr)).where(Referral.referrer_id == user_id)
        result = await db.scalar(query)
        return float(result or 0.0)

referral_repository = ReferralRepository(Referral)