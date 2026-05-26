import asyncio
import json
import os
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import text

from backend.db.session import async_session_factory
from backend.models.user import User
from backend.models.transaction import Transaction
from backend.models.issuer import Issuer
from backend.models.sticker import StickerCatalog, UserSticker
from backend.models.enums import Currency, TransactionType, TransactionStatus
from backend.services.tournament import tournament_service
from backend.core.redis import redis_service

async def main():
    print("🚀 Starting Tournament Distribution Field Test...")
    
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    start_time = now_utc - timedelta(hours=2)
    end_time = now_utc - timedelta(minutes=10) # 10 минут назад - турнир окончен
    
    async with async_session_factory() as db:
        print("\n[1] Creating Dummy Issuer...")
        issuer = Issuer(
            slug=f"test_issuer_{random.randint(1000, 9999)}",
            name="Test Tourney Issuer",
        )
        db.add(issuer)
        await db.flush()
        
        print(f"[2] Creating 5 Dummy Users and Transactions (Start: {start_time}, End: {end_time})...")
        users = []
        volumes = [500, 400, 300, 200, 100]
        
        for i, vol in enumerate(volumes):
            user = User(
                telegram_id=random.randint(10000000, 99999999),
                username=f"tourney_tester_{i+1}",
                balance_ton=0.0
            )
            db.add(user)
            users.append(user)
            
        await db.flush()
        
        # Транзакции
        for i, user in enumerate(users):
            tx = Transaction(
                user_id=user.id,
                amount=volumes[i],
                currency=Currency.TON,
                type=TransactionType.OPEN_CASE,
                status=TransactionStatus.COMPLETED
            )
            db.add(tx)
        
        await db.flush()
        
        # Жестко прописываем время транзакций, чтобы они точно попали в турнир
        tx_time = start_time + timedelta(minutes=30)
        for i, user in enumerate(users):
            await db.execute(
                text("UPDATE transactions SET created_at = :t WHERE user_id = :uid"),
                {"t": tx_time, "uid": str(user.id).replace("-", "")}
            )
            
        print("[3] Creating Dummy Prize Stickers...")
        catalogs = []
        stickers = []
        for i in range(3):
            cat = StickerCatalog(
                issuer_id=issuer.id,
                name=f"Prize Catalog {i+1}",
                image_url="https://test.com/prize.png"
            )
            db.add(cat)
            catalogs.append(cat)
            
        await db.flush()
        
        for i in range(3):
            st = UserSticker(
                catalog_id=catalogs[i].id,
                number=random.randint(100000, 999999),
                is_available=True,
                owner_id=None
            )
            db.add(st)
            stickers.append(st)
            
        await db.commit()
        
        print("\n[4] Configuring tournament_config.json...")
        config_path = os.path.join(os.getcwd(), "tournament_config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception:
            config = {"Tournament": {"Setting": {}, "PrizeByPlace": {}}}
            
        start_str = start_time.strftime("%d.%m.%Y %H:%M:%S")
        end_str = end_time.strftime("%d.%m.%Y %H:%M:%S")
        
        config["Tournament"]["Setting"]["start_time"] = start_str
        config["Tournament"]["Setting"]["end_time"] = end_str
        config["Tournament"]["Setting"]["is_distributed"] = False
        config["Tournament"]["Setting"]["max_place"] = 50
        
        config["Tournament"]["PrizeByPlace"] = {
            "1": {
                "catalog_id": str(catalogs[0].id),
                "sticker_pool_id": str(stickers[0].id)
            },
            "2": {
                "catalog_id": str(catalogs[1].id),
                "sticker_pool_id": str(stickers[1].id)
            },
            "3": {
                "catalog_id": str(catalogs[2].id),
                "sticker_pool_id": str(stickers[2].id)
            },
            "else": {
                "ton_balance": "+0.77"
            }
        }
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
            
        print(f"Tournament set: {start_str} - {end_str}")
        print("Prizes configured: Top 3 get stickers, else gets 0.77 TON")
        
        print("\n[5] Triggering Distribution Logic...")
        await redis_service.connect()
        await tournament_service.update_leaderboard()
        
        print("\n[6] Verifying Results...")
        for i, user in enumerate(users):
            await db.refresh(user)
            place = i + 1
            if place <= 3:
                await db.refresh(stickers[i])
                if stickers[i].owner_id == user.id:
                    print(f"✅ Place {place} ({user.username}): SUCCESS - Received Sticker {stickers[i].id}")
                else:
                    print(f"❌ Place {place} ({user.username}): FAILED - Did not receive sticker")
            else:
                if user.balance_ton == 0.77:
                    print(f"✅ Place {place} ({user.username}): SUCCESS - Received 0.77 TON (Balance: {user.balance_ton})")
                else:
                    print(f"❌ Place {place} ({user.username}): FAILED - Did not receive TON (Balance: {user.balance_ton})")

if __name__ == "__main__":
    asyncio.run(main())