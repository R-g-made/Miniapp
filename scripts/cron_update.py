import asyncio
import sys
from pathlib import Path
from loguru import logger

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from backend.db.session import async_session_factory
from backend.services.floor_price_service import floor_price_service

async def run_update():
    logger.info("Starting scheduled floor and chance update...")
    async with async_session_factory() as db:
        try:
            # Обновляет флор из GetGems/Tools + пересчитывает шансы и цены кейсов
            await floor_price_service.update_all_prices(db)
            logger.success("Scheduled update completed successfully.")
        except Exception as e:
            logger.error(f"Scheduled update failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_update())