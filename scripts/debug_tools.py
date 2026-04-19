import httpx
from loguru import logger
import json


async def debug_tools():
    logger.info("Fetching data from stickers.tools...")
    
    headers = {
        "User-Agent": "sticker-floor-bot/2.0",
        "Accept": "application/json",
        "Referer": "https://stickers.tools/",
        "Origin": "https://stickers.tools",
    }
    
    api_url = "https://api.stickers.tools/all_floors"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(api_url, headers=headers)
            response.raise_for_status()
            payload = response.json()
            
            logger.info(f"Success! Found {len(payload.get('collections', {}))} collections!")
            
            # Сохраняем в файл для анализа
            with open("tools_data.json", "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            
            logger.info("Saved to tools_data.json!")
            
            # Показываем первые 5 коллекций
            collections = payload.get("collections", {})
            for i, (key, col) in enumerate(list(collections.items())[:5]):
                logger.info(f"Collection #{i+1}: {col.get('name')}")
                stickers = col.get("stickers") or {}
                for j, (s_key, s) in enumerate(list(stickers.items())[:3]):
                    logger.info(f"  Sticker #{j+1}: {s.get('name')}")
                    
        except Exception as e:
            logger.error(f"Failed: {e}")
            import traceback
            logger.error(traceback.format_exc())


if __name__ == "__main__":
    import asyncio
    asyncio.run(debug_tools())
