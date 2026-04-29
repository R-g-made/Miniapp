import sys
import os
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import httpx
import asyncio
import json
from loguru import logger
from backend.core.config import settings
from backend.services.thermos_service import thermos_service

async def fetch_stickers_tools():
    url = "https://stickers.tools/api/stats-new"
    headers = {
        "User-Agent": "sticker-floor-bot/2.0",
        "Accept": "application/json",
        "Referer": "https://stickers.tools/",
        "Origin": "https://stickers.tools",
    }
    logger.info(f"--- Тест STICKERS.TOOLS ({url}) ---")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            with open("debug_stickers_tools.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.success("Ответ Stickers.tools сохранен в debug_stickers_tools.json")
            return data
        except Exception as e:
            logger.error(f"Ошибка Stickers.tools: {e}")
            return None

async def fetch_thermos():
    logger.info("--- Тест THERMOS API ---")
    try:
        data = await thermos_service.get_my_stickers()
        if data is not None:
            with open("debug_thermos.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.success("Ответ Thermos сохранен в debug_thermos.json")
            return data
        else:
            logger.error("Thermos вернул None")
            return None
    except Exception as e:
        logger.error(f"Ошибка Thermos: {e}")
        return None

async def fetch_tonapi():
    merchant_address = settings.MERCHANT_TON_ADDRESS
    if not merchant_address:
        logger.warning("MERCHANT_TON_ADDRESS не задан, пропускаю тест Tonapi")
        return None
        
    url = f"https://{'testnet.' if settings.IS_TESTNET else ''}tonapi.io/v2/accounts/{merchant_address}/nfts"
    headers = {"Authorization": f"Bearer {settings.TON_API_KEY}"} if settings.TON_API_KEY else {}
    
    logger.info(f"--- Тест TONAPI ({url}) ---")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            with open("debug_tonapi.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.success("Ответ Tonapi сохранен в debug_tonapi.json")
            return data
        except Exception as e:
            logger.error(f"Ошибка Tonapi: {e}")
            return None

async def run_all_tests():
    logger.info("Запуск полного теста всех внешних API...")
    
    # Запускаем всё параллельно
    await asyncio.gather(
        fetch_stickers_tools(),
        fetch_thermos(),
        fetch_tonapi()
    )
    
    logger.success("\nВсе тесты завершены. Проверьте файлы: debug_stickers_tools.json, debug_thermos.json, debug_tonapi.json")

if __name__ == "__main__":
    asyncio.run(run_all_tests())