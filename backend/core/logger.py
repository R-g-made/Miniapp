import sys
from loguru import logger
import os

def setup_logging():
    """
    Профессиональная настройка логирования с использованием loguru.
    """
    # Удаляем стандартный обработчик, чтобы не было дублей
    logger.remove()

    # 1. Настройка вывода в консоль (красивый текстовый формат для разработки)
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<magenta>{extra[request_id]}</magenta> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stdout,
        format=console_format,
        level="INFO",
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # 2. Настройка вывода в JSON файл (для продакшена и анализа)
    # Создаем папку для логов, если её нет
    os.makedirs("logs", exist_ok=True)
    
    logger.add(
        "logs/app.json",
        format="{time} {level} {message} {extra}",
        level="DEBUG",
        serialize=True,  # Превращает лог в структурированный JSON
        rotation="100 MB",
        retention="10 days",
        compression="zip",
    )

    # Добавляем дефолтный request_id для логов вне контекста запроса
    logger.configure(extra={"request_id": "SYSTEM"})

setup_logging()
