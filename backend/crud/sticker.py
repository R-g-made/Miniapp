from typing import List, Tuple, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from backend.crud.base import BaseRepository
from backend.models.sticker import UserSticker, StickerCatalog
from backend.models.issuer import Issuer
from backend.models.transaction import Transaction

from datetime import datetime
from backend.core.config import settings

from backend.core.exceptions import EntityNotFound, InvalidOperation, InsufficientFunds

class StickerRepository(BaseRepository[UserSticker]):
    async def get_user_stickers(
        self,
        db: AsyncSession,
        user_id: UUID,
        skip: int = 0,
        limit: int = 10,
        issuer_slug: Optional[str] = None
    ) -> Tuple[List[UserSticker], int]:
        query = select(UserSticker).where(UserSticker.owner_id == user_id)
        
        if issuer_slug:
            query = query.join(UserSticker.catalog).join(StickerCatalog.issuer).where(Issuer.slug == issuer_slug)
        
        query = query.options(
            selectinload(UserSticker.catalog).selectinload(StickerCatalog.issuer)
        )
        
        count_query = select(func.count(UserSticker.id)).where(UserSticker.owner_id == user_id)
        if issuer_slug:
            count_query = count_query.join(UserSticker.catalog).join(StickerCatalog.issuer).where(Issuer.slug == issuer_slug)
            
        total = await db.scalar(count_query) or 0
        
        #сначала новые
        query = query.order_by(UserSticker.created_at.desc()).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all(), total

    async def get_with_details(self, db: AsyncSession, sticker_id: UUID) -> Optional[UserSticker]:
        """
        Получает стикер с подгруженными связями (каталог, владелец).
        """
        stmt = select(UserSticker).options(
            selectinload(UserSticker.catalog),
            selectinload(UserSticker.owner)
        ).where(UserSticker.id == sticker_id)
        
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_random_from_pool(self, db: AsyncSession, catalog_id: UUID) -> Optional[UserSticker]:
        """
        Получает случайный свободный стикер из пула для данного каталога.
        """
        # Выбираем один случайный стикер, где owner_id is None и is_available is True
        query = select(UserSticker).where(
            UserSticker.catalog_id == catalog_id,
            UserSticker.owner_id == None,
            UserSticker.is_available == True
        ).order_by(func.random()).limit(1)
        
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def count_available_in_pool(self, db: AsyncSession, catalog_id: UUID) -> int:
        """
        Считает количество доступных стикеров в пуле для конкретного каталога.
        """
        # Сначала посчитаем вообще все стикеры этого каталога для отладки
        from loguru import logger
        total_stmt = select(func.count(UserSticker.id)).where(UserSticker.catalog_id == catalog_id)
        total_in_db = await db.scalar(total_stmt) or 0
        
        query = select(func.count(UserSticker.id)).where(
            UserSticker.catalog_id == catalog_id,
            UserSticker.owner_id == None,
            UserSticker.is_available == True
        )
        result = await db.execute(query)
        available = result.scalar() or 0
        
        if total_in_db > 0 and available == 0:
            logger.warning(f"StickerCRUD: Catalog {catalog_id} has {total_in_db} total stickers, but 0 are available (archived or owned)!")
            
        return available

    async def get_all_pool_counts(self, db: AsyncSession) -> List[Tuple[UUID, int]]:
        """
        Считает количество доступных стикеров в пуле для всех каталогов.
        Возвращает список кортежей (catalog_id, count).
        """
        query = select(
            UserSticker.catalog_id,
            func.count(UserSticker.id)
        ).where(
            UserSticker.owner_id == None,
            UserSticker.is_available == True
        ).group_by(UserSticker.catalog_id)
        
        result = await db.execute(query)
        return result.all()

    async def get_all_catalogs(self, db: AsyncSession) -> List[StickerCatalog]:
        """Получить все элементы каталога"""
        query = select(StickerCatalog)
        result = await db.execute(query)
        return result.scalars().all()

    async def update_catalog_floor_price(
        self, 
        db: AsyncSession, 
        catalog_id: UUID, 
        ton_price: float = None, 
        stars_price: float = None,
        commit: bool = True
    ):
        """Обновить флор-прайс в каталоге"""
        query = select(StickerCatalog).where(StickerCatalog.id == catalog_id)
        result = await db.execute(query)
        catalog = result.scalar_one_or_none()
        if catalog:
            if ton_price is not None:
                catalog.floor_price_ton = ton_price
            if stars_price is not None:
                catalog.floor_price_stars = stars_price
            db.add(catalog)
            if commit:
                await db.commit()

sticker = StickerRepository(UserSticker)