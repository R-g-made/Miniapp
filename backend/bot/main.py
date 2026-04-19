import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.core.config import settings
from backend.bot.handlers import common
from loguru import logger

class BotBuilder:
    def __init__(self, token: str):
        self.bot = Bot(token=token, parse_mode=ParseMode.HTML)
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
    
    # Инициализация планировщика
    scheduler = AsyncIOScheduler()
    
    from backend.services.market_buy_service import market_buy_service
    from backend.services.floor_price_service import floor_price_service
    from backend.services.refund_service import refund_service
    from backend.services.notification_service import notification_service
    from backend.services.case_service import case_service
    from backend.db.session import async_session_factory
    
    # Инициализируем сервис уведомлений
    notification_service.set_bot(bot)
    
    # # async def auto_buy_job():
    #     logger.info("Running auto-buy job...")
    #     async with async_session_factory() as db:
    #         await market_buy_service.run_auto_buy(db)
            
    async def floor_check_job():
        logger.info("Running floor check job...")
        async with async_session_factory() as db:
            await floor_price_service.update_all_prices(db)

    async def refund_check_job():
        logger.info("Running refund check job...")
        async with async_session_factory() as db:
            await refund_service.check_refunds(db, bot)

    async def case_recovery_job():
        logger.info("Running case recovery job...")
        async with async_session_factory() as db:
            await case_service.check_inactive_cases(db)

    # Добавляем задачи
    # scheduler.add_job(
    #     auto_buy_job, 
    #     "interval", 
    #     hours=settings.AUTO_BUY_INTERVAL_HOURS
    # )
    scheduler.add_job(
        floor_check_job, 
        "interval", 
        hours=settings.FLOOR_CHECK_INTERVAL_HOURS
    )
    scheduler.add_job(
        refund_check_job,
        "interval",
        minutes=settings.REFUND_CHECK_INTERVAL_MINUTES
    )
    scheduler.add_job(
        case_recovery_job,
        "interval",
        minutes=settings.CASE_RECOVERY_CHECK_INTERVAL_MINUTES
    )
    
    logger.info("Starting scheduler...")
    scheduler.start()
    
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
