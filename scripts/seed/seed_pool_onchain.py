import sys
import os
import re
import httpx
from pathlib import Path
from loguru import logger
from sqlalchemy import select

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(root_dir))

# Проверяем аргументы командной строки до импортов бэкенда
if "--sqlite" in sys.argv:
    os.environ["USE_SQLITE"] = "True"
    os.environ["USE_REDIS"] = "False"

import asyncio
from backend.db.session import async_session_factory, engine
from backend.models.sticker import StickerCatalog, UserSticker
from backend.models.base import Base
from backend.core.config import settings

async def fetch_wallet_nfts(address: str) -> list:
    """Получает список NFT кошелька через Tonapi"""
    base_url = "https://testnet.tonapi.io/v2" if settings.IS_TESTNET else "https://tonapi.io/v2"
    url = f"{base_url}/accounts/{address}/nfts"
    
    headers = {}
    if settings.TON_API_KEY:
        headers["Authorization"] = f"Bearer {settings.TON_API_KEY}"
        
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data.get("nft_items", [])
        except Exception as e:
            logger.error(f"Failed to fetch NFTs for {address}: {e}")
            return []

def extract_number(name: str) -> int:
    """Извлекает номер из имени NFT (например, 'Pudgy #123')"""
    match = re.search(r'#(\d+)', name)
    if match:
        return int(match.group(1))
    return 0

async def seed_pool_onchain():
    logger.info("Starting sticker pool seed from Blockchain (TON NFTs)...")

    if "--sqlite" in sys.argv:
        logger.info("Initializing tables for SQLite...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    # 1. Получаем адрес мерчанта из настроек
    merchant_address = settings.MERCHANT_TON_ADDRESS
    if not merchant_address:
        logger.error("MERCHANT_TON_ADDRESS not set in config.")
        return

    # 2. Получаем NFT кошелька
    nfts = await fetch_wallet_nfts(merchant_address)
    if not nfts:
        logger.warning(f"No NFTs found for wallet {merchant_address}")
        return

    logger.info(f"Found {len(nfts)} NFTs in wallet {merchant_address}")

    async with async_session_factory() as db:
        # 3. Загружаем каталог для сопоставления по адресу коллекции
        stmt = select(StickerCatalog).where(StickerCatalog.collection_address != None)
        result = await db.execute(stmt)
        catalog_items = result.scalars().all()
        
        # Маппинг адрес_коллекции -> catalog_item
        # Нормализуем адреса для сравнения
        from ton_core import Address
        
        catalog_map = {}
        for c in catalog_items:
            try:
                norm_addr = Address(c.collection_address).to_str(is_user_friendly=False)
                catalog_map[norm_addr] = c
            except:
                continue

        added_count = 0
        updated_count = 0
        skipped_count = 0

        for nft in nfts:
            nft_address = nft.get("address")
            collection = nft.get("collection", {})
            coll_address = collection.get("address")
            
            if not nft_address or not coll_address:
                continue
                
            # Нормализуем адрес коллекции NFT
            try:
                norm_coll_addr = Address(coll_address).to_str(is_user_friendly=False)
            except:
                continue
                
            catalog = catalog_map.get(norm_coll_addr)
            if not catalog:
                # logger.debug(f"No catalog item found for collection {coll_address}")
                continue

            # Извлекаем номер из метаданных (name)
            metadata = nft.get("metadata", {})
            name = metadata.get("name", "")
            number = extract_number(name)
            
            # 4. Проверяем на дубликаты по nft_address
            stmt = select(UserSticker).where(UserSticker.nft_address == nft_address)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Если уже есть, проверяем статус
                if not existing.is_onchain:
                    existing.is_onchain = True
                    existing.is_available = True
                    updated_count += 1
                else:
                    skipped_count += 1
                continue

            # 5. Создаем новую запись
            new_pool_item = UserSticker(
                catalog_id=catalog.id,
                number=number,
                is_available=True,
                is_onchain=True,
                nft_address=nft_address,
                ton_price=catalog.floor_price_ton,
                stars_price=catalog.floor_price_stars,
                owner_id=None
            )
            db.add(new_pool_item)
            added_count += 1

        await db.commit()
        logger.success(f"Pool seed from Blockchain completed: added {added_count}, updated {updated_count}, skipped {skipped_count} duplicates.")

if __name__ == "__main__":
    asyncio.run(seed_pool_onchain())
