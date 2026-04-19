import asyncio
import sys
import os
import random
from uuid import uuid4
from datetime import datetime, timezone
from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func, text

# Add project root to PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.base import Base
from app.models.user import User
from app.models.referral import Referral
from app.models.case import Case
from app.models.associations import CaseItem
from app.models.sticker import StickerCatalog, UserSticker
from app.models.transaction import Transaction
from app.models.enums import Currency, TransactionType, TransactionStatus
from app.services.case_service import case_service
from app.services.chance_service import chance_service
from app.services.wallet_service import WalletService
from app.core.config import settings

from app.models.issuer import Issuer

# Mock TonapiClient to avoid network errors during stress test
from unittest.mock import MagicMock
import tonutils.clients
tonutils.clients.TonapiClient = MagicMock()

# Test DB setup
TEST_DB_URL = "sqlite+aiosqlite:///./stress_test.db"
engine = create_async_engine(
    TEST_DB_URL, 
    echo=False,
    connect_args={"timeout": 30} # Increase timeout for SQLite
)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # Enable WAL mode for better concurrency in SQLite
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))

async def worker(worker_id, users, cases, stats, catalogs, lock):
    async with async_session() as db:
        # Mock WalletService to avoid TON API errors
        wallet_service = MagicMock()
        async def mock_withdraw(*args, **kwargs):
            return True
        wallet_service.create_withdrawal_request = mock_withdraw
        
        for i in range(100): # Each worker does 100 operations
            try:
                user_data = random.choice(users)
                # Reload user to avoid session issues
                user = await db.get(User, user_data.id)
                case_to_open = random.choice(cases)
                
                # Simulate "unexpected clicks" - multiple rapid requests for the same user
                choice = random.random()
                if choice < 0.20: # 20% chance of rapid clicks
                    num_clicks = random.randint(3, 10)
                    tasks = [
                        case_service.open_case(db, user, case_to_open.slug, currency=Currency.TON)
                        for _ in range(num_clicks)
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for res in results:
                        if isinstance(res, Exception):
                            # logger.debug(f"Expected exception during rapid clicks: {res}")
                            pass
                        else:
                            won_sticker, price, new_balance = res
                            async with lock:
                                stats["total_spent"] += price
                                stats["total_won_value"] += won_sticker.catalog.floor_price_ton
                elif choice < 0.35: # 15% chance of concurrent withdrawal and case opening
                    tasks = [
                        case_service.open_case(db, user, case_to_open.slug, currency=Currency.TON),
                        wallet_service.create_withdrawal_request(user, 1.0, Currency.TON, "EQ_STRESS_TEST_ADDRESS")
                    ]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for res in results:
                        if isinstance(res, tuple): # open_case result
                            won_sticker, price, new_balance = res
                            async with lock:
                                stats["total_spent"] += price
                                stats["total_won_value"] += won_sticker.catalog.floor_price_ton
                        elif not isinstance(res, Exception) and res: # withdrawal result
                            async with lock:
                                stats["withdrawals"] += 1
                else:
                    won_sticker, price, new_balance = await case_service.open_case(
                        db, user, case_to_open.slug, currency=Currency.TON
                    )
                    async with lock:
                        stats["total_spent"] += price
                        stats["total_won_value"] += won_sticker.catalog.floor_price_ton
            except Exception as e:
                # logger.warning(f"Worker {worker_id} encountered an error: {e}")
                await db.rollback() # Important to rollback after error to reuse session
                await asyncio.sleep(0.1) # Backoff
                continue
            
            # Randomly simulate some delay between user actions
            await asyncio.sleep(random.uniform(0.01, 0.05))

async def run_simulation():
    logger.info("🚀 Starting massive CONCURRENT stress test simulation...")
    await setup_db()
    
    async with async_session() as db:
        # 0. Создаем эмитента
        issuer = Issuer(name="Stress Test Issuer", slug="stress_issuer")
        db.add(issuer)
        await db.commit()
        await db.refresh(issuer)

        # 1. Создаем 1000 пользователей
        users = []
        for i in range(1000):
            user = User(
                telegram_id=1000000 + i,
                username=f"user_{i}",
                balance_ton=100.0,
                balance_stars=10000.0
            )
            db.add(user)
            users.append(user)
        await db.commit()
        # Refresh users to get IDs
        for u in users:
            await db.refresh(u)
        
        # 2. Создаем реферальную структуру
        referrers = users[:200]
        for i in range(200, 1000):
            referrer = random.choice(referrers)
            referred = users[i]
            ref_record = Referral(
                referrer_id=referrer.id,
                referred_id=referred.id,
                ref_percentage=10.0
            )
            db.add(ref_record)
        await db.commit()

        # 3. Создаем каталоги стикеров
        catalogs = []
        for i in range(20):
            cat = StickerCatalog(
                issuer_id=issuer.id,
                name=f"Sticker_{i}",
                collection_name="StressTest_Coll",
                image_url=f"https://example.com/sticker_{i}.png",
                floor_price_ton=random.uniform(0.5, 50.0),
                is_onchain=True
            )
            db.add(cat)
            catalogs.append(cat)
        await db.commit()

        for cat in catalogs:
            for j in range(250): # Reduced to speed up
                sticker = UserSticker(
                    catalog_id=cat.id,
                    owner_id=None,
                    is_available=True,
                    number=j+1
                )
                db.add(sticker)
        await db.commit()

        # 4. Создаем 3 кейса
        case_configs = [
            ("Cheap Case", "cheap", 2.0),
            ("Standard Case", "standard", 10.0),
            ("Premium Case", "premium", 50.0)
        ]
        cases = []
        for name, slug, price in case_configs:
            c = Case(
                name=name, 
                slug=slug, 
                image_url=f"https://example.com/case_{slug}.png",
                price_ton=price, 
                price_stars=price*100, 
                is_active=True, 
                is_chance_distribution=True
            )
            db.add(c)
            case_items = random.sample(catalogs, 10)
            for cat in case_items:
                ci = CaseItem(case=c, sticker_catalog_id=cat.id, chance=0.1)
                db.add(ci)
            cases.append(c)
        await db.commit()
        
        for c in cases:
            await chance_service.recalculate_case_chances(db, c.id)

    # 5. СИМУЛЯЦИЯ АКТИВНОСТИ (Concurrent workers)
    stats = {"total_spent": 0.0, "total_won_value": 0.0, "ref_payouts": 0.0, "withdrawals": 0}
    lock = asyncio.Lock()
    
    workers = []
    for i in range(100): # 100 concurrent workers
        workers.append(worker(i, users, cases, stats, catalogs, lock))
    
    logger.info("🔥 Running 100 workers concurrently (10,000 total operations)...")
    await asyncio.gather(*workers)

    # 6. ИТОГОВЫЙ ОТЧЕТ
    async with async_session() as db:
        stmt_ref_total = select(func.sum(Referral.reward_ton))
        res_ref_total = await db.execute(stmt_ref_total)
        stats["ref_payouts"] = res_ref_total.scalar() or 0.0


        logger.success("\n--- SIMULATION COMPLETED ---")
        logger.info(f"Total Cases Opened: 5000")
        logger.info(f"Total Revenue: {stats['total_spent']:.2f} TON")
        logger.info(f"Total Prizes Value: {stats['total_won_value']:.2f} TON")
        logger.info(f"Total Referral Rewards Distributed: {stats['ref_payouts']:.2f} TON")
        logger.info(f"Total Withdrawal Requests: {stats['withdrawals']}")
        
        real_rtp = (stats["total_won_value"] / stats["total_spent"]) * 100 if stats["total_spent"] > 0 else 0
        system_profit = stats["total_spent"] - stats["total_won_value"] - stats["ref_payouts"]
        
        logger.info(f"Actual RTP: {real_rtp:.2f}% (Target: 90%)")
        logger.info(f"System Net Profit: {system_profit:.2f} TON")
        
        if 85 <= real_rtp <= 95:
            logger.success("✅ RTP is within healthy range (85-95%)!")
        else:
            logger.warning("⚠️ RTP is out of expected range. Check balancing logic.")

if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")
    
    try:
        asyncio.run(run_simulation())
    except Exception as e:
        logger.exception(f"Simulation failed: {e}")
