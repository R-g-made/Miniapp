import sys
import os
from pathlib import Path
import re
import uuid
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

from backend.db.session import async_session_factory
from backend.models.sticker import StickerCatalog, PriorityMarket
from backend.models.issuer import Issuer


def parse_final_catalog():
    """Парсим FinalCatalog.md и возвращаем список стикеров."""
    catalog_path = Path(__file__).parent / "FinalCatalog.md"
    if not catalog_path.exists():
        raise FileNotFoundError(f"FinalCatalog.md not found at {catalog_path}")

    with open(catalog_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    stickers = []
    current_collection = None
    current_sticker = None

    for line in lines:
        line = line.rstrip("\n")
        
        # Парсим заголовок коллекции (##)
        if line.startswith("## "):
            coll_name = line[3:].strip()
            if coll_name.endswith("Case"):
                coll_name = coll_name[:-5].strip()
            current_collection = coll_name
            continue
        
        # Парсим заголовок стикера (###)
        if line.startswith("### "):
            # Сохраняем предыдущий стикер, если есть
            if current_sticker and current_sticker.get("image_url"):
                stickers.append(current_sticker)
            
            full_title = line[4:].strip()
            
            # Парсим: все что до первого "-" это коллекция, все что после это имя
            sticker_name = full_title
            sticker_collection = current_collection
            
            if " - " in full_title:
                parts = full_title.split(" - ", 1)
                # Проверяем, не является ли первая часть слишком короткой (чтобы не сломать существующие)
                if len(parts[0].strip()) > 0:
                    sticker_collection = parts[0].strip()
                    sticker_name = parts[1].strip()
            
            # Начинаем новый стикер
            current_sticker = {
                "name": sticker_name,
                "collection_name": sticker_collection,
                "collection_address": None,
                "max_pool_size": 5,
                "lottie_url": None,
                "image_url": None,
                "issuer_slug": "goodies"
            }
            continue
        
        # Парсим атрибуты стикера
        if current_sticker is None:
            continue
            
        line_stripped = line.strip()
        
        if line_stripped.startswith("- Collection Address:"):
            current_sticker["collection_address"] = line_stripped.split(":", 1)[1].strip()
        elif line_stripped.startswith("- Max Pool:"):
            mp_str = line_stripped.split(":", 1)[1].strip()
            try:
                current_sticker["max_pool_size"] = int(mp_str)
            except ValueError:
                current_sticker["max_pool_size"] = 5
        elif line_stripped.startswith("- Issusier:"):
            issuer_name = line_stripped.split(":", 1)[1].strip()
            if issuer_name == "Sticker Store":
                current_sticker["issuer_slug"] = "stickerstore"
            elif issuer_name == "Goodies":
                current_sticker["issuer_slug"] = "goodies"
            elif issuer_name == "Elephant Store":
                current_sticker["issuer_slug"] = "elephantstore"
            elif issuer_name == "StickerStore":
                current_sticker["issuer_slug"] = "stickerstore"
        elif line_stripped.startswith("- [") or line_stripped.startswith("  - ["):
            url_match = re.search(r"\((https?://[^\)]+)\)", line_stripped)
            if url_match:
                url = url_match.group(1)
                if url.endswith(".json"):
                    current_sticker["lottie_url"] = url
                elif url.endswith(".webp") or url.endswith(".png") or url.endswith(".jpg"):
                    current_sticker["image_url"] = url

    # Сохраняем последний стикер
    if current_sticker and current_sticker.get("image_url"):
        stickers.append(current_sticker)

    logger.info(f"Found {len(stickers)} stickers in FinalCatalog.md")
    return stickers


async def seed_catalog():
    logger.info("Starting catalog seed...")
    stickers_data = parse_final_catalog()
    logger.info(f"Parsed {len(stickers_data)} stickers from FinalCatalog.md")

    async with async_session_factory() as db:
        for sticker_data in stickers_data:
            # Получаем эмитента по slug
            issuer_stmt = select(Issuer).where(Issuer.slug == sticker_data["issuer_slug"])
            issuer_result = await db.execute(issuer_stmt)
            issuer = issuer_result.scalar_one_or_none()

            if not issuer:
                logger.warning(f"Issuer not found for slug {sticker_data['issuer_slug']}, skipping sticker {sticker_data['name']}")
                continue

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
