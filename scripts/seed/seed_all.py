import sys
import os
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import asyncio
from loguru import logger

from scripts.seed_issuers import seed_issuers
from scripts.seed_catalog import seed_catalog


async def main():
    logger.info("=== Starting full seed ===")
    
    # Сначала сидим эмитентов
    await seed_issuers()
    
    # Потом сидим каталог стикеров
    await seed_catalog()
    
    logger.info("=== Full seed completed successfully! ===")


if __name__ == "__main__":
    asyncio.run(main())
