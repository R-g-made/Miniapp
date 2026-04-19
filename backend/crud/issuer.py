from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.crud.base import BaseRepository
from backend.models.issuer import Issuer

class IssuerRepository(BaseRepository[Issuer]):
    async def get_all_active(self, db: AsyncSession) -> List[Issuer]:
        query = select(self.model)
        result = await db.execute(query)
        return result.scalars().all()

issuer = IssuerRepository(Issuer)