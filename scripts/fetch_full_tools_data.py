import asyncio
import httpx
import json
import sys
import os
from loguru import logger

# Add project root to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.config import settings

async def fetch_stickers_tools_data():
    url = settings.STICKERS_TOOLS_API_URL
    headers = {
        "User-Agent": "sticker-floor-bot/2.0",
        "Accept": "application/json",
        "Referer": "https://stickers.tools/",
        "Origin": "https://stickers.tools",
    }
    
    logger.info(f"Fetching data from {url}...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Сохраняем полный ответ в файл для детального изучения
            with open("stickers_tools_full_data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.success("Full data saved to stickers_tools_full_data.json")
            
            # Выводим структуру данных в консоль (верхний уровень)
            logger.info(f"Data keys: {list(data.keys())}")
            
            if "collections" in data:
                collections = data["collections"]
                logger.info(f"Number of collections: {len(collections)}")
                
                # Выведем детальную информацию по первым 2 коллекциям для примера
                sample_count = 0
                for col_id, col_data in collections.items():
                    if sample_count >= 2:
                        break
                    
                    logger.info(f"\n--- Collection ID: {col_id} ---")
                    # Выводим всё содержимое коллекции кроме, возможно, очень длинных списков
                    col_summary = {k: v for k, v in col_data.items() if k != 'stickers'}
                    logger.info(f"Metadata: {json.dumps(col_summary, indent=2, ensure_ascii=False)}")
                    
                    if "stickers" in col_data:
                        stickers = col_data["stickers"]
                        logger.info(f"Number of sticker packs: {len(stickers)}")
                        
                        # Пример одного пака
                        if stickers:
                            first_pack_id = list(stickers.keys())[0]
                            logger.info(f"First pack ({first_pack_id}) full data: {json.dumps(stickers[first_pack_id], indent=2, ensure_ascii=False)}")
                    
                    sample_count += 1
            
        except Exception as e:
            logger.error(f"Failed to fetch data: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_stickers_tools_data())
