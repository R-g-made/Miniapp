import asyncio
import sys
import os
from sqlalchemy import select
from loguru import logger

# Добавляем корень проекта в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.session import async_session_factory
from backend.models.sticker import StickerCatalog, ThermosMapping
from backend.services.thermos_service import thermos_service

async def populate_thermos_mappings():
    """
    Скрипт для наполнения таблицы thermos_mappings.
    Сопоставляет наши StickerCatalog с данными из API Thermos по имени.
    """
    logger.info("Starting Thermos mapping population...")
    
    async with async_session_factory() as db:
        # 1. Получаем все наши оффчейн коллекции
        query = select(StickerCatalog).where(StickerCatalog.is_onchain == False)
        result = await db.execute(query)
        catalogs = result.scalars().all()
        
        if not catalogs:
            logger.info("No off-chain catalogs found in DB to map.")
            return

        logger.info(f"Found {len(catalogs)} off-chain catalogs in DB.")
        
        # 2. Получаем полный каталог от Thermos
        thermos_catalog = await thermos_service.get_market_catalog()
        if not thermos_catalog:
            logger.error("Could not fetch Thermos catalog for mapping.")
            return

        logger.info(f"Fetched {len(thermos_catalog)} items from Thermos catalog.")

        mapped_count = 0
        for catalog in catalogs:
            # Ищем совпадение по имени или названию коллекции
            search_name = catalog.name.lower()
            collection_name = (catalog.collection_name or "").lower()
            
            best_match = None
            for item in thermos_catalog:
                item_name = item.get("name", "").lower()
                
                # Точное совпадение имени или если имя содержит название нашей коллекции + имя
                if search_name == item_name or (collection_name and f"{collection_name} {search_name}" == item_name):
                    best_match = item
                    break
                # Частичное совпадение
                if search_name in item_name:
                    best_match = item
            
            if best_match:
                t_collection_id = best_match.get("collection_id")
                t_character_id = best_match.get("character_id")
                
                if t_collection_id is not None and t_character_id is not None:
                    # Проверяем, существует ли уже маппинг
                    stmt = select(ThermosMapping).where(ThermosMapping.catalog_id == catalog.id)
                    existing = (await db.execute(stmt)).scalar_one_or_none()
                    
                    if existing:
                        existing.thermos_collection_id = t_collection_id
                        existing.thermos_character_id = t_character_id
                        existing.thermos_collection_name = best_match.get("collection_name")
                        existing.thermos_character_name = best_match.get("character_name") or best_match.get("name")
                        logger.info(f"Updated mapping for '{catalog.name}': [Col:{t_collection_id}, Char:{t_character_id}]")
                    else:
                        new_mapping = ThermosMapping(
                            catalog_id=catalog.id,
                            thermos_collection_id=t_collection_id,
                            thermos_character_id=t_character_id,
                            thermos_collection_name=best_match.get("collection_name"),
                            thermos_character_name=best_match.get("character_name") or best_match.get("name")
                        )
                        db.add(new_mapping)
                        logger.info(f"Created new mapping for '{catalog.name}': [Col:{t_collection_id}, Char:{t_character_id}]")
                    
                    mapped_count += 1
            else:
                logger.warning(f"Could not find a match for '{catalog.name}' in Thermos catalog.")

        if mapped_count > 0:
            await db.commit()
            logger.success(f"Mapping completed! Successfully mapped {mapped_count} catalogs.")
        else:
            logger.info("Mapping completed. No new matches found.")

if __name__ == "__main__":
    # Настройка логирования
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    asyncio.run(populate_thermos_mappings())
