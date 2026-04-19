import sys
import os
from pathlib import Path
from loguru import logger

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


def test_seed_parsing_simple():
    """Простой тест - проверим парсинг вручную на нескольких примерах"""
    logger.info("=== Тест парсинга названий стикеров ===")
    
    test_cases = [
        "Shiba Inu - Shib: Army Infantry",
        "BONK - BONK: The Dog",
        "Pudgy Penguins - Ice Pengu",
        "Cook",
        "Blue Wings"
    ]
    
    for full_title in test_cases:
        sticker_name = full_title
        sticker_collection = "Default"
        
        if " - " in full_title:
            parts = full_title.split(" - ", 1)
            if len(parts[0].strip()) > 0:
                sticker_collection = parts[0].strip()
                sticker_name = parts[1].strip()
        
        logger.info(f"Вход: '{full_title}'")
        logger.info(f"  Коллекция: '{sticker_collection}'")
        logger.info(f"  Имя: '{sticker_name}'")
        logger.info("")
    
    logger.success("=== Тест завершен! ===")


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    try:
        test_seed_parsing_simple()
    except Exception as e:
        logger.exception(f"❌ Ошибка: {e}")
