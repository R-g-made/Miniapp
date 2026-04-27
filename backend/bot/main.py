import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from backend.core.config import settings
from backend.bot.handlers import common
from loguru import logger

class BotBuilder:
    def __init__(self, token: str):
        self.bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.dp = Dispatcher()

    def with_handlers(self):
        self.dp.include_router(common.router)
        return self

    def build(self) -> tuple[Bot, Dispatcher]:
        return self.bot, self.dp

async def run_bot():
    bot, dp = (
        BotBuilder(token=settings.BOT_TOKEN)
        .with_handlers()
        .build()
    )
    
    from backend.services.notification_service import notification_service
    
    # Инициализируем сервис уведомлений
    notification_service.set_bot(bot)
    
    logger.info("Starting bot...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging_config = {
        "handlers": [
            {"sink": sys.stdout, "format": "{time} {level} {message}"},
        ],
    }
    logger.configure(**logging_config)
    asyncio.run(run_bot())
