import sys
import os
from pathlib import Path
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from backend.db.session import async_session_factory
from backend.services.floor_price_service import floor_price_service


async def update_floors():
    logger.info("Starting floor price update...")
    
    async with async_session_factory() as db:
        await floor_price_service.update_all_prices(db)
    
    logger.info("Floor price update completed successfully!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(update_floors())
