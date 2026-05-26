from sqlalchemy import select, func, desc, case
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.transaction import Transaction
from backend.models.user import User
from backend.models.enums import TransactionType, Currency, TransactionStatus
from backend.core.config import settings
from uuid import UUID
from datetime import datetime
from typing import List, Tuple

class CRUDTournament:
    async def get_top_users_by_volume(
        self, 
        db: AsyncSession, 
        start_time: datetime, 
        end_time: datetime, 
        limit: int = 50,
        ignore_user_ids: List[str] = None
    ) -> List[Tuple[User, float]]:
        # Перевод Stars в TON для правильного объема
        volume_expr = func.sum(
            case(
                (Transaction.currency == Currency.TON.value, Transaction.amount),
                (Transaction.currency == Currency.STARS.value, Transaction.amount * settings.STARS_TO_TON_RATE),
                else_=0.0
            )
        ).label("total_volume")

        stmt = (
            select(User, volume_expr)
            .join(Transaction, Transaction.user_id == User.id)
            .where(
                Transaction.type == TransactionType.OPEN_CASE.value,
                Transaction.created_at >= start_time,
                Transaction.created_at <= end_time,
                Transaction.status == TransactionStatus.COMPLETED.value
            )
        )

        if ignore_user_ids:
            ignore_uuids = []
            for uid in ignore_user_ids:
                try:
                    ignore_uuids.append(UUID(uid))
                except Exception:
                    pass
            if ignore_uuids:
                stmt = stmt.where(User.id.notin_(ignore_uuids))

        stmt = (
            stmt.group_by(User.id)
            .having(volume_expr > 0)
            .order_by(desc("total_volume"), User.created_at)
            .limit(limit)
        )

        result = await db.execute(stmt)
        return result.all()
        
    async def get_user_volume(
        self,
        db: AsyncSession,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime
    ) -> float:
        """Получить объём конкретного пользователя (если он не в ТОП-50)"""
        volume_expr = func.sum(
            case(
                (Transaction.currency == Currency.TON.value, Transaction.amount),
                (Transaction.currency == Currency.STARS.value, Transaction.amount * settings.STARS_TO_TON_RATE),
                else_=0.0
            )
        )

        stmt = (
            select(volume_expr)
            .where(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.OPEN_CASE.value,
                Transaction.created_at >= start_time,
                Transaction.created_at <= end_time,
                Transaction.status == TransactionStatus.COMPLETED.value
            )
        )
        result = await db.execute(stmt)
        val = result.scalar()
        return float(val) if val else 0.0

tournament_crud = CRUDTournament()