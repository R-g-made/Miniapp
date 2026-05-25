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
        self._tasks.append(asyncio.create_task(self._run_ton_deposits_check()))
        self._tasks.append(asyncio.create_task(self._run_tournament_worker()))
        
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

    async def _run_ton_deposits_check(self):
        logger.info("TonDeposits Worker: Started (Interval: 10s)")
        
        while True:
            try:
                from backend.models.transaction import TonDeposit, Transaction
                from backend.models.enums import TransactionStatus, TransactionType, Currency
                from backend.services.user_service import user_service
                from datetime import timedelta
                
                async with async_session_factory() as db:
                    # 1. Mark older than 24h as EXPIRED
                    expiration_time = datetime.now(timezone.utc) - timedelta(hours=24)
                    stmt_expire = update(TonDeposit).where(
                        TonDeposit.status == TransactionStatus.PENDING,
                        TonDeposit.created_at < expiration_time.replace(tzinfo=None)
                    ).values(status=TransactionStatus.EXPIRED)
                    await db.execute(stmt_expire)
                    await db.commit()
                    
                    # 2. Check if there are any PENDING deposits
                    stmt_pending = select(TonDeposit).where(TonDeposit.status == TransactionStatus.PENDING).limit(1)
                    has_pending = (await db.execute(stmt_pending)).scalar_one_or_none()
                    
                    if has_pending:
                        import httpx
                        from ton_core import Address
                        
                        base_url = "https://testnet.tonapi.io/v2" if settings.IS_TESTNET else "https://tonapi.io/v2"
                        headers = {}
                        if settings.TON_API_KEY:
                            headers["Authorization"] = f"Bearer {settings.TON_API_KEY}"
                            
                        merchant_addr_hex = Address(settings.MERCHANT_TON_ADDRESS).to_str(is_user_friendly=False)
                        
                        url = f"{base_url}/accounts/{settings.MERCHANT_TON_ADDRESS}/events?limit=50"
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            resp = await client.get(url, headers=headers)
                            if resp.status_code == 200:
                                data = resp.json()
                                events = data.get("events", [])
                                
                                for event in events:
                                    if event.get("in_progress", False):
                                        continue
                                        
                                    for action in event.get("actions", []):
                                        if action.get("type") == "TonTransfer":
                                            transfer = action.get("ton_transfer") or action.get("TonTransfer")
                                            if not transfer: continue
                                            
                                            recipient = transfer.get("recipient", {})
                                            recipient_addr = recipient.get("address") if isinstance(recipient, dict) else recipient
                                            if not recipient_addr: continue
                                            
                                            try:
                                                norm_recipient = Address(recipient_addr).to_str(is_user_friendly=False)
                                            except Exception:
                                                continue
                                                
                                            if norm_recipient != merchant_addr_hex:
                                                continue
                                                
                                            comment = transfer.get("comment")
                                            if not comment: continue
                                            
                                            amount_nano = int(transfer.get("amount", 0))
                                            
                                            # Lookup pending deposit by mnemonic (comment)
                                            stmt_dep = select(TonDeposit).where(
                                                TonDeposit.status == TransactionStatus.PENDING,
                                                TonDeposit.mnemonic == comment
                                            )
                                            deposit = (await db.execute(stmt_dep)).scalar_one_or_none()
                                            
                                            if deposit:
                                                expected_nano = deposit.amount_ton * 10**9
                                                # Check 5% margin
                                                if amount_nano >= (expected_nano * 0.95):
                                                    # Complete deposit
                                                    deposit.status = TransactionStatus.COMPLETED
                                                    
                                                    # Check if transaction with this event_id already exists
                                                    event_id = event.get("event_id")
                                                    stmt_tx = select(Transaction).where(Transaction.hash == event_id)
                                                    existing_tx = (await db.execute(stmt_tx)).scalar_one_or_none()
                                                    
                                                    if not existing_tx:
                                                        user = await user_service.get_locked(db, deposit.user_id)
                                                        if user:
                                                            actual_ton = round(amount_nano / 10**9, 9)
                                                            user.balance_ton = float(user.balance_ton) + actual_ton
                                                            
                                                            tx = Transaction(
                                                                user_id=user.id,
                                                                amount=actual_ton,
                                                                currency=Currency.TON,
                                                                type=TransactionType.DEPOSIT,
                                                                status=TransactionStatus.COMPLETED,
                                                                hash=event_id,
                                                                details={"onchain_data": str(event)}
                                                            )
                                                            db.add(tx)
                                                            db.add(user)
                                                            db.add(deposit)
                                                            
                                                            try:
                                                                await db.commit()
                                                                
                                                                # Send WS update
                                                                from backend.core.websocket_manager import manager
                                                                from backend.schemas.websocket import WSEventMessage
                                                                from backend.models.enums import WSMessageType
                                                                await manager.send_to_user(
                                                                    user_id=str(user.id),
                                                                    message=WSEventMessage(
                                                                        type=WSMessageType.BALANCE_UPDATE,
                                                                        data={
                                                                            "currency": Currency.TON.value,
                                                                            "new_balance": float(user.balance_ton)
                                                                        }
                                                                    )
                                                                )
                                                                logger.success(f"TonDeposits Worker: Confirmed deposit {deposit.id} for user {user.id}")
                                                            except Exception as e:
                                                                await db.rollback()
                                                                logger.error(f"TonDeposits Worker: Failed to commit deposit {deposit.id}: {e}")
            except Exception as e:
                logger.error(f"TonDeposits Worker Global Error: {e}")
            
            await asyncio.sleep(10)

    async def _run_tournament_worker(self):
        logger.info("Tournament Worker: Started")
        lock_key = "tournament_worker_lock"
        import uuid
        instance_id = str(uuid.uuid4())
        
        while True:
            try:
                from backend.services.tournament import tournament_service
                settings = tournament_service.get_settings()
                check_interval = settings.get("check_interval", 300) if settings else 300
                
                await asyncio.sleep(check_interval)
                
                if not tournament_service.is_active():
                    continue

                try:
                    redis_client = await redis_service.connect()
                    lock_duration = int(check_interval * 0.8)
                    is_locked = await redis_client.set(lock_key, instance_id, nx=True, ex=lock_duration)
                    if not is_locked:
                        current_owner = await redis_client.get(lock_key)
                        if current_owner != instance_id: continue
                        await redis_client.expire(lock_key, lock_duration)
                except Exception:
                    pass
                
                await tournament_service.update_leaderboard()
            except Exception as e:
                logger.error(f"Tournament Worker Error: {e}")
                await asyncio.sleep(60)

worker_service = WorkerService()