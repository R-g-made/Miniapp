import asyncio
import sys
import os
from loguru import logger

# Добавляем корень проекта в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.thermos_service import thermos_service

async def test_auth_and_stickers():
    """
    Тестовый скрипт для проверки аутентификации Thermos и получения списка своих стикеров.
    """
    logger.info("Starting Thermos Auth & Stickers test...")
    
    # 1. Проверяем наличие токена
    if not thermos_service.api_token:
        logger.error("THERMOS_API_TOKEN not found in settings! Add it to .env file.")
        return

    try:
        # 2. Получаем список стикеров (метод сам вызовет аутентификацию)
        logger.info("Calling get_my_stickers()...")
        stickers = await thermos_service.get_my_stickers()
        
        if stickers is not None:
            logger.success(f"Successfully fetched {len(stickers)} stickers from Thermos!")
            if len(stickers) > 0:
                for i, sticker in enumerate(stickers[:5]):
                    name = sticker.get('name') or sticker.get('unique_name')
                    price = sticker.get('price')
                    logger.info(f"Sticker {i+1}: {name} (Price: {price} nanoTON)")
            else:
                logger.info("Your account has 0 stickers on Thermos.")
        else:
            logger.error("Failed to fetch stickers (received None)")
            
    except Exception as e:
        logger.exception(f"Test failed with error: {e}")

if __name__ == "__main__":
    # Настройка логирования
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    asyncio.run(test_auth_and_stickers())
