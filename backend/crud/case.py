from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, asc
from sqlalchemy.orm import selectinload, joinedload
from backend.crud.base import BaseRepository
from backend.models.case import Case
from backend.models.associations import CaseIssuer, CaseItem
from backend.models.issuer import Issuer
from backend.models.sticker import StickerCatalog

class CaseRepository(BaseRepository[Case]):
    async def get_catalog(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        sort_by: Optional[str] = None,
        issuer_slug: Optional[str] = None,
        only_active: bool = True
    ) -> List[Case]:
        query = select(Case).options(
            selectinload(Case.issuer_associations).selectinload(CaseIssuer.issuer),
            selectinload(Case.items).selectinload(CaseItem.sticker_catalog)
        )
        
        if only_active:
            query = query.where(Case.is_active == True)

        if issuer_slug:
            # Фильтр по слагу эмитента через join
            query = query.join(Case.issuer_associations).join(CaseIssuer.issuer).where(Issuer.slug == issuer_slug)
            
            # Если сортировка не задана явно, сортируем: сначала где он главный, потом остальные
            if not sort_by:
                # CaseIssuer.is_main desc (True first)
                query = query.order_by(desc(CaseIssuer.is_main), desc(Case.created_at))
        
        # Явная сортировка или дефолтная (если не фильтруем по эмитенту без сортировки)
        if sort_by:
            if sort_by == "price_asc":
                query = query.order_by(asc(Case.price_ton))
            elif sort_by == "price_desc":
                query = query.order_by(desc(Case.price_ton))
            elif sort_by == "newest":
                query = query.order_by(desc(Case.created_at))
            elif sort_by == "oldest":
                query = query.order_by(asc(Case.created_at))
        elif not issuer_slug:
             # Дефолтная сортировка: сначала новые
            query = query.order_by(desc(Case.created_at))

        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()

    async def get_by_slug(self, db: AsyncSession, slug: str) -> Optional[Case]:
        query = select(Case).where(Case.slug == slug, Case.is_active == True).options(
            selectinload(Case.items).selectinload(CaseItem.sticker_catalog)
        )
        result = await db.execute(query)
        return result.scalars().first()

case = CaseRepository(Case)