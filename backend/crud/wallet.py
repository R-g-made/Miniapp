from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.crud.base import BaseRepository
from backend.models.wallet import Wallet
from backend.schemas.wallet import WalletCreate

class CRUDWallet(BaseRepository[Wallet]):
    async def get_by_address(self, db: AsyncSession, *, address: str) -> Optional[Wallet]:
        """Поиск активного кошелька по адресу"""
        result = await db.execute(
            select(self.model).where(
                self.model.address == address,
                self.model.is_active == True
            )
        )
        return result.scalars().first()

    async def get_active_by_owner_id(self, db: AsyncSession, *, owner_id: str) -> Optional[Wallet]:
        """Поиск единственного активного кошелька пользователя"""
        result = await db.execute(
            select(self.model).where(
                self.model.owner_id == owner_id,
                self.model.is_active == True
            )
        )
        return result.scalars().first()

    async def deactivate_active_wallet(self, db: AsyncSession, *, owner_id: str, commit: bool = True) -> bool:
        """Деактивация активного кошелька пользователя (soft delete)"""
        result = await db.execute(
            update(self.model)
            .where(self.model.owner_id == owner_id, self.model.is_active == True)
            .values(is_active=False)
        )
        if commit:
            await db.commit()
        return result.rowcount > 0

wallet_repository = CRUDWallet(Wallet)
