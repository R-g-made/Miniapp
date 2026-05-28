import asyncio
import sys
import os

# Добавляем корневую директорию проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Bot, types
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import select
from backend.core.config import settings
from backend.db.session import async_session_factory
from backend.models.user import User
from loguru import logger

PHOTO_URL = "https://i.ibb.co/QFzjVMLq/Salee.jpg"
MESSAGE_TEXT = (
    "<b>Loot-турнир запущен 🐥</b>\n\n"
    "С 27 Мая до 3 Июня 50 лучших игроков получат награды:\n\n"
    "1 место — Freedom 🧢\n"
    "2 место — DOGS King 👑\n"
    "3 место — Ponke Day Ones 🐒\n\n"
    "Остальные призы будут распределены среди топ-50.\n\n"
    "<b>Система подсчета очков:</b>\n\n"
    "— Каждый 1 TON, потраченный на покупку пака, равен 1 TON в таблице лидеров.\n"
    "— Чем больше паков открыто, тем выше ваша позиция в списке."
)

async def broadcast():
    bot = Bot(token=settings.BOT_TOKEN)
    
    # Кнопка для открытия турнира
    # Для Telegram Mini App используем параметр startapp
    tournament_url = settings.MINI_APP_URL
            
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(
        text="Участвовать в Турнире", 
        url=tournament_url
    ))
    
    async with async_session_factory() as db:
        # Получаем всех пользователей
        query = select(User.telegram_id)
        result = await db.execute(query)
        user_ids = result.scalars().all()
        
    logger.info(f"Начинаем рассылку для {len(user_ids)} пользователей...")
    
    success_count = 0
    blocked_count = 0
    error_count = 0
    
    for user_id in user_ids:
        try:
            await bot.send_photo(
                chat_id=user_id,
                photo=PHOTO_URL,
                caption=MESSAGE_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=builder.as_markup()
            )
            success_count += 1
            if success_count % 10 == 0:
                logger.info(f"Прогресс: {success_count} сообщений отправлено")
            
            # Небольшая задержка, чтобы не превысить лимиты Telegram (30 сообщений в секунду)
            await asyncio.sleep(0.05)
            
        except TelegramForbiddenError:
            blocked_count += 1
        except TelegramRetryAfter as e:
            logger.warning(f"Превышен лимит запросов. Ожидание {e.retry_after} секунд")
            await asyncio.sleep(e.retry_after)
            # Можно повторить попытку
            try:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=PHOTO_URL,
                    caption=MESSAGE_TEXT,
                    parse_mode=ParseMode.HTML,
                    reply_markup=builder.as_markup()
                )
                success_count += 1
            except Exception:
                error_count += 1
        except Exception as e:
            logger.error(f"Ошибка при отправке пользователю {user_id}: {e}")
            error_count += 1
            
    logger.info(f"Рассылка завершена!")
    logger.info(f"Успешно: {success_count}")
    logger.info(f"Заблокировали бота: {blocked_count}")
    logger.info(f"Ошибки: {error_count}")
    
    await bot.session.close()

if __name__ == "__main__":
    # Настройка логирования
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    try:
        asyncio.run(broadcast())
    except KeyboardInterrupt:
        logger.warning("Рассылка прервана пользователем")
