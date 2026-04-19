import sys
import os
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

import asyncio
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.session import async_session_factory
from backend.models.issuer import Issuer


async def seed_issuers():
    logger.info("Starting issuers seed...")
    
    # Данные из Issusier.md
    issuers_data = [
        {
            "name": "Sticker Store",
            "slug": "stickerstore",
            "icon_url": "https://i.ibb.co/DHdFgRxQ/Sticker-pack-logo.jpg"
        },
        {
            "name": "Goodies",
            "slug": "goodies",
            "icon_url": "https://i.ibb.co/JWQPbDpp/Goodies-logo.jpg"
        },
        {
            "name": "Elephant Store",
            "slug": "elephantstore",
            "icon_url": "https://i.ibb.co/gZy0LhCK/Slon-icon.jpg"
        }
    ]
    
    async with async_session_factory() as db:
        for issuer_data in issuers_data:
            # Проверяем, существует ли уже эмитент по slug
            stmt = select(Issuer).where(Issuer.slug == issuer_data["slug"])
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.info(f"Issuer already exists, skipping: {issuer_data['name']}")
                continue
            
            # Создаем новый эмитент
            logger.info(f"Creating new issuer: {issuer_data['name']}")
            new_issuer = Issuer(
                name=issuer_data["name"],
                slug=issuer_data["slug"],
                icon_url=issuer_data["icon_url"]
            )
            db.add(new_issuer)
        
        await db.commit()
        logger.info("Issuers seed completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_issuers())
