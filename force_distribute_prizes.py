import asyncio
import sys
import os

# Добавляем корень проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.tournament import tournament_service
from loguru import logger

async def force_distribute():
    logger.info("Начинаем принудительную раздачу призов...")
    # Метод update_leaderboard сам проверит, что время вышло и флаг is_distributed = false
    await tournament_service.update_leaderboard()
    logger.info("Процесс завершен. Проверьте логи на наличие ошибок или подтверждения раздачи.")

if __name__ == "__main__":
    asyncio.run(force_distribute())