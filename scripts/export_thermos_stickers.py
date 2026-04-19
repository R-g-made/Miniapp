import asyncio
import sys
import os
import json
from loguru import logger

# Добавляем корень проекта в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.thermos_service import thermos_service

async def export_my_stickers_to_json():
    """
    Скрипт для получения полного списка стикеров с Thermos и сохранения их в JSON файл.
    """
    logger.info("Starting Thermos stickers export to JSON...")
    
    # 1. Проверяем наличие токена
    if not thermos_service.api_token:
        logger.error("THERMOS_API_TOKEN not found in settings! Add it to .env file.")
        return

    try:
        # 2. Получаем список стикеров
        logger.info("Fetching stickers from Thermos API...")
        stickers = await thermos_service.get_my_stickers()
        
        if stickers is not None:
            count = len(stickers)
            logger.success(f"Successfully fetched {count} stickers from Thermos!")
            
            # 3. Сохраняем в JSON файл
            output_file = "my_thermos_stickers.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(stickers, f, ensure_ascii=False, indent=4)
            
            logger.info(f"Full list of stickers has been saved to: {os.path.abspath(output_file)}")
            
            if count > 0:
                logger.info("Sample data from the first sticker:")
                sample = stickers[0]
                # Выводим ключи для понимания структуры
                logger.info(f"Fields available: {list(sample.keys())}")
        else:
            logger.error("Failed to fetch stickers (received None)")
            
    except Exception as e:
        logger.exception(f"Export failed with error: {e}")

if __name__ == "__main__":
    # Настройка логирования
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    asyncio.run(export_my_stickers_to_json())
