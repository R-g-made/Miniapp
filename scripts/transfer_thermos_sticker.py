import asyncio
import sys
import os
import json
from loguru import logger

# Добавляем корень проекта в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.thermos_service import thermos_service

async def transfer_sticker_to_tg():
    """
    Скрипт для трансфера конкретного стикера на Telegram ID.
    Стикер: collection_id: 4, character_id: 1, instance: 389
    """
    logger.info("Starting Thermos sticker transfer script...")
    
    # 1. Проверяем наличие токена
    if not thermos_service.api_token:
        logger.error("THERMOS_API_TOKEN not found in settings! Add it to .env file.")
        return

    # 2. Формируем полезную нагрузку (payload)
    # По данным из JSON: collection_id: 4, character_id: 1, instance: 389
    target_tg_id = 1131784912
    
    payload = {
        "owned_stickers": [
            {
                "collection_id": 4,
                "character_id": 1,
                "instance": 389,
                "collection_name": None,
                "character_name": None
            }
        ],
        "withdraw": False, # Убрали withdraw True
        "target_telegram_user_id": target_tg_id,
        "wallet_address": None,
        "anonymous": False
    }

    try:
        # 3. Вызываем метод трансфера
        logger.info(f"Transferring sticker [4:1:{389}] to TG ID {target_tg_id}...")
        result = await thermos_service.transfer_sticker(payload)
        
        logger.success("Transfer initiated successfully!")
        logger.info(f"API Response: {json.dumps(result, indent=2)}")
        
    except Exception as e:
        logger.exception(f"Transfer failed with error: {e}")

if __name__ == "__main__":
    # Настройка логирования
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    asyncio.run(transfer_sticker_to_tg())
