import sys
import os
from pathlib import Path
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from backend.db.session import async_session_factory
from backend.models.case import Case
from backend.models.associations import CaseItem, CaseIssuer
from backend.models.sticker import StickerCatalog
from backend.models.issuer import Issuer


async def seed_case():
    logger.info("Starting case seed...")
    
    case_slug = "all-stickers-case"
    case_name = "All Stickers Case"
    case_price_ton = 1.0
    case_price_stars = 50.0
    
    async with async_session_factory() as db:
        # Проверяем, существует ли уже кейс
        stmt = select(Case).where(Case.slug == case_slug)
        result = await db.execute(stmt)
        existing_case = result.scalar_one_or_none()
        
        if existing_case:
            logger.info(f"Case already exists, skipping: {case_name}")
            return
        
        # Получаем все стикеры из каталога
        catalog_stmt = select(StickerCatalog)
        catalog_result = await db.execute(catalog_stmt)
        all_stickers = catalog_result.scalars().all()
        
        if not all_stickers:
            logger.error("No stickers found in catalog!")
            return
        
        logger.info(f"Found {len(all_stickers)} stickers in catalog")
        
        # Получаем главного эмитента (Goodies)
        issuer_stmt = select(Issuer).where(Issuer.slug == "goodies")
        issuer_result = await db.execute(issuer_stmt)
        main_issuer = issuer_result.scalar_one_or_none()
        
        if not main_issuer:
            logger.error("Main issuer (goodies) not found!")
            return
        
        # Создаем новый кейс
        new_case = Case(
            slug=case_slug,
            name=case_name,
            image_url="https://i.ibb.co/JWQPbDpp/Goodies-logo.jpg",
            price_ton=case_price_ton,
            price_stars=case_price_stars,
            is_active=True,
            is_chance_distribution=False,
            styles={}
        )
        db.add(new_case)
        await db.flush()
        await db.refresh(new_case)
        
        # Добавляем эмитента
        case_issuer = CaseIssuer(
            case_id=new_case.id,
            issuer_id=main_issuer.id,
            is_main=True
        )
        db.add(case_issuer)
        
        # Добавляем все стикеры в кейс с равными шансами
        chance_per_item = 1.0 / len(all_stickers)
        for sticker in all_stickers:
            case_item = CaseItem(
                case_id=new_case.id,
                sticker_catalog_id=sticker.id,
                chance=chance_per_item
            )
            db.add(case_item)
        
        await db.commit()
        logger.info(f"Case '{case_name}' created successfully with {len(all_stickers)} items!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_case())
