import sys
import os
from pathlib import Path
import re
import uuid
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent
sys.path.insert(0, str(root_dir))

from backend.db.session import async_session_factory
from backend.models.sticker import StickerCatalog, PriorityMarket
from backend.models.issuer import Issuer


def parse_final_catalog():
    """Парсим FinalCatalog.md и возвращаем список стикеров."""
    catalog_path = root_dir / "FinalCatalog.md"
    if not catalog_path.exists():
        raise FileNotFoundError(f"FinalCatalog.md not found at {catalog_path}")

    with open(catalog_path, "r", encoding="utf-8") as f:
        content = f.read()

    stickers = []
    current_collection = None

    sections = content.split("## ")
    for section in sections:
        if not section.strip():
            continue

        # Парсим коллекцию (заголовок ##)
        lines = section.split("\n")
        if lines[0].strip():
            current_collection = lines[0].strip()
            if current_collection.endswith("Case"):
                current_collection = current_collection[:-5].strip()

        # Парсим стикеры (###)
        sticker_blocks = re.split(r"### ", section)
        for sticker_block in sticker_blocks[1:]:
            sticker_lines = sticker_block.split("\n")
            if not sticker_lines[0].strip():
                continue

            name = sticker_lines[0].strip()
            collection_address = None
            max_pool = 5  # Дефолт
            lottie_url = None
            image_url = None

            for line in sticker_lines[1:]:
                line = line.strip()
                if line.startswith("- Collection Address:"):
                    collection_address = line.split(":", 1)[1].strip()
                elif line.startswith("- Max Pool:"):
                    mp = line.split(":", 1)[1].strip()
                    try:
                        max_pool = int(mp)
                    except ValueError:
                        max_pool = 5
                elif line.startswith("  - ["):
                    # Парсим ссылки на ассеты
                    url_match = re.search(r"\((https?://[^\)]+)\)", line)
                    if url_match:
                        url = url_match.group(1)
                        if url.endswith(".json"):
                            lottie_url = url
                        elif url.endswith(".webp") or url.endswith(".png") or url.endswith(".jpg"):
                            image_url = url

            if not image_url:
                logger.warning(f"No image URL for sticker {name}")
                continue

            stickers.append({
                "name": name,
                "collection_name": current_collection,
                "image_url": image_url,
                "lottie_url": lottie_url,
                "collection_address": collection_address,
                "max_pool_size": max_pool,
                "issuer_name": current_collection or "Unknown"
            })

    return stickers


async def seed_catalog():
    logger.info("Starting catalog seed...")
    stickers_data = parse_final_catalog()
    logger.info(f"Parsed {len(stickers_data)} stickers from FinalCatalog.md")

    async with async_session_factory() as db:
        # Создаем или получаем эмитента для каждого sticker
        for sticker_data in stickers_data:
            # Получаем или создаем эмитент
            issuer_stmt = select(Issuer).where(Issuer.name == sticker_data["issuer_name"])
            issuer_result = await db.execute(issuer_stmt)
            issuer = issuer_result.scalar_one_or_none()

            if not issuer:
                logger.info(f"Creating new issuer: {sticker_data['issuer_name']}")
                issuer = Issuer(
                    name=sticker_data["issuer_name"],
                    slug=sticker_data["issuer_name"].lower().replace(" ", "-").replace("(", "").replace(")", ""),
                    description=f"Issuer for {sticker_data['issuer_name']}"
                )
                db.add(issuer)
                await db.flush()
                await db.refresh(issuer)

            # Проверяем, есть ли уже этот стикер в каталоге
            catalog_stmt = select(StickerCatalog).where(
                StickerCatalog.name == sticker_data["name"],
                StickerCatalog.issuer_id == issuer.id
            )
            catalog_result = await db.execute(catalog_stmt)
            existing = catalog_result.scalar_one_or_none()

            if existing:
                logger.info(f"Sticker already exists, skipping: {sticker_data['name']}")
                continue

            # Создаем новый стикер в каталоге
            logger.info(f"Adding new sticker to catalog: {sticker_data['name']}")
            new_catalog = StickerCatalog(
                issuer_id=issuer.id,
                name=sticker_data["name"],
                collection_name=sticker_data["collection_name"],
                image_url=sticker_data["image_url"],
                lottie_url=sticker_data["lottie_url"],
                collection_address=sticker_data["collection_address"],
                max_pool_size=sticker_data["max_pool_size"],
                priority_market=PriorityMarket.LAFFKA,
                is_onchain=bool(sticker_data["collection_address"])
            )
            db.add(new_catalog)

        await db.commit()
        logger.info("Catalog seed completed successfully!")


if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_catalog())
