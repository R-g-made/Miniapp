import asyncio
import random
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy import select, func, update
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from backend.core.config import settings
from backend.core.redis import redis_service
from backend.db.session import async_session_factory
from backend.models.sticker import StickerCatalog
from backend.services.referral_service import ReferralService
from backend.services.floor_price_service import floor_price_service
from backend.services.live_drop_service import live_drop_service
from backend.services.sticker_service import sticker_service
from backend.services.refund_service import refund_service
from backend.services.case_service import case_service
from backend.services.notification_service import notification_service

class WorkerService:
    """
    Единый сервис для управления всеми фоновыми воркерами приложения.
    """
    def __init__(self):
        self._tasks = []
        self._bot = None

    async def start_all(self):
        """Запуск всех фоновых задач"""
        logger.info("WorkerService: Initializing background workers...")
        
        if settings.BOT_TOKEN:
            try:
                self._bot = Bot(
                    token=settings.BOT_TOKEN, 
                    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
                )
                notification_service.set_bot(self._bot)
                logger.info("WorkerService: Bot initialized and set to NotificationService")
            except Exception as e:
                logger.error(f"WorkerService: Failed to initialize bot: {e}")

        self._tasks.append(asyncio.create_task(self._run_live_drops()))
        self._tasks.append(asyncio.create_task(self._run_fast_checks_loop()))
        self._tasks.append(asyncio.create_task(self._run_maintenance_loop()))
        
        logger.success(f"WorkerService: {len(self._tasks)} workers started successfully.")

    async def _run_live_drops(self):
        logger.info(f"LiveDrop Worker: Started (Interval: {settings.LIVE_DROP_INTERVAL}s)")
        import uuid
        instance_id = str(uuid.uuid4())
        lock_key = "live_drops_generator_lock"
        
        while True:
            try:
                jitter = random.uniform(0.8, 1.2)
                await asyncio.sleep(settings.LIVE_DROP_INTERVAL * jitter)
                
                try:
                    redis_client = await redis_service.connect()
                    lock_duration = int(settings.LIVE_DROP_INTERVAL * 2)
                    is_locked = await redis_client.set(lock_key, instance_id, nx=True, ex=lock_duration)
                    if not is_locked:
                        current_owner = await redis_client.get(lock_key)
                        if current_owner != instance_id: continue
                        await redis_client.expire(lock_key, lock_duration)
                except Exception as e:
                    if settings.USE_REDIS: continue

                async with async_session_factory() as db:
                    from backend.models.case import Case
                    from backend.models.associations import CaseItem
                    
                    # Ищем стикеры только из АКТИВНЫХ кейсов
                    query = (
                        select(StickerCatalog)
                        .join(CaseItem, CaseItem.sticker_catalog_id == StickerCatalog.id)
                        .join(Case, Case.id == CaseItem.case_id)
                        .where(Case.is_active == True)
                        .order_by(func.random())
                        .limit(1)
                    )
                    
                    result = await db.execute(query)
                    catalog = result.scalar_one_or_none()
                    if catalog:
                        await live_drop_service.add_drop(
                            image_url=catalog.image_url,
                            floor_price_ton=catalog.floor_price_ton or 0.0
                        )
            except Exception as e:
                logger.error(f"LiveDrop Worker Error: {e}")
                await asyncio.sleep(5)

    async def _run_fast_checks_loop(self):
        interval_min = settings.CASE_RECOVERY_INTERVAL_MINUTES
        logger.info(f"FastChecks Worker: Started (Interval: {interval_min} minutes)")
        
        while True:
            try:
                async with async_session_factory() as db:
                    await case_service.check_inactive_cases(db)
            except Exception as e:
                logger.error(f"FastChecks Worker Global Error: {e}")
            await asyncio.sleep(interval_min * 60)

    async def _run_maintenance_loop(self):
        logger.info(f"Maintenance Worker: Started (Interval: {settings.MAINTENANCE_INTERVAL_HOURS} hours)")
        while True:
            try:
                async with async_session_factory() as db:
                    logger.info("Maintenance Worker: Running scheduled tasks...")
                    
                    # 1. Проверка рефаундов Stars
                    if self._bot:
                        try:
                            await refund_service.check_refunds(db, self._bot)
                        except Exception as e:
                            logger.error(f"Maintenance Worker: Refund check failed: {e}")

                    # 2. Обновление Floor Prices и пересчет RTP/шансов
                    try:
                        await floor_price_service.update_all_prices(db)
                    except Exception as e:
                        logger.error(f"Maintenance Worker: Floor update failed: {e}")
                    
                    # 3. Разблокировки и синхронизация пула
                    ref_service = ReferralService(db)
                    await ref_service.process_unlocks()
                    await sticker_service.process_sticker_unlocks(db)

                    try:
                        sync_res = await sticker_service.sync_pool_with_external_sources(db)
                        total_added = sync_res["thermos_added"] + sync_res["onchain_added"]
                        if total_added > 0:
                            logger.success(f"Maintenance Worker: Refilled pool with {total_added} new stickers.")
                            await case_service.check_inactive_cases(db)
                    except Exception as e:
                        logger.error(f"Maintenance Worker: Pool sync failed: {e}")
                    
                    logger.success("Maintenance Worker: Cycle completed.")
            except Exception as e:
                logger.error(f"Maintenance Worker Global Error: {e}")
            await asyncio.sleep(settings.MAINTENANCE_INTERVAL_HOURS * 3600)

worker_service = WorkerService()