import sys
import os
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

# Проверяем аргументы командной строки до импортов бэкенда
if "--sqlite" in sys.argv:
    os.environ["USE_SQLITE"] = "True"
    os.environ["USE_REDIS"] = "False"

import asyncio
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.session import async_session_factory, engine
from backend.models.issuer import Issuer
from backend.models.base import Base

def parse_issuers():
    """Парсим Issusier.md и возвращаем список эмитентов."""
    issuers_path = Path(__file__).parent / "Issusier.md"
    if not issuers_path.exists():
        logger.error(f"Issusier.md not found at {issuers_path}")
        return []

    with open(issuers_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    
    # Разделяем блоки по двойному переносу строки
    blocks = content.split('\n\n')
    issuers = []
    
    for block in blocks:
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if len(lines) >= 3:
            issuers.append({
                "name": lines[0],
                "slug": lines[1],
                "icon_url": lines[2]
            })
    
    return issuers

async def seed_issuers():
    logger.info("Starting issuers seed from Issusier.md...")
    
    if "--sqlite" in sys.argv:
        logger.info("Initializing tables for SQLite...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    issuers_data = parse_issuers()
    if not issuers_data:
        logger.warning("No issuers found to seed.")
        return
    
    async with async_session_factory() as db:
        for issuer_data in issuers_data:
            # Проверяем, существует ли уже эмитент по slug
            stmt = select(Issuer).where(Issuer.slug == issuer_data["slug"])
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # Обновляем данные если они изменились
                updated = False
                if existing.name != issuer_data["name"]:
                    existing.name = issuer_data["name"]
                    updated = True
                if existing.icon_url != issuer_data["icon_url"]:
                    existing.icon_url = issuer_data["icon_url"]
                    updated = True
                
                if updated:
                    logger.info(f"Updated issuer: {issuer_data['name']}")
                else:
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
