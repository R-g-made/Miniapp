import json
import os
from datetime import datetime, timezone
from uuid import UUID
from loguru import logger
from sqlalchemy import select

from backend.core.redis import redis_service
from backend.db.session import async_session_factory
from backend.crud.tournament import tournament_crud
from backend.models.sticker import StickerCatalog

CONFIG_PATH = os.path.join(os.getcwd(), "tournament_config.json")
REDIS_KEY = "tournament_leaderboard"

class TournamentService:
    def _load_config(self) -> dict:
        if not os.path.exists(CONFIG_PATH):
            return {}
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"TournamentService: Failed to load config - {e}")
            return {}

    def _save_config(self, config: dict):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"TournamentService: Failed to save config - {e}")

    def get_settings(self) -> dict:
        config = self._load_config()
        return config.get("Tournament", {}).get("Setting", {})

    def get_prizes(self) -> dict:
        config = self._load_config()
        return config.get("Tournament", {}).get("PrizeByPlace", {})

    def get_reserved_sticker_ids(self) -> list[UUID]:
        prizes = self.get_prizes()
        reserved = []
        for place, prize_data in prizes.items():
            if isinstance(prize_data, dict):
                pool_id = prize_data.get("sticker_pool_id")
                if pool_id:
                    try:
                        reserved.append(UUID(pool_id))
                    except Exception:
                        pass
        return reserved

    def is_active(self) -> bool:
        settings = self.get_settings()
        if not settings:
            return False
        
        start_str = settings.get("start_time")
        end_str = settings.get("end_time")
        if not start_str or not end_str:
            return False
            
        try:
            start_time = datetime.strptime(start_str, "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc)
            end_time = datetime.strptime(end_str, "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            return start_time <= now <= end_time
        except ValueError as e:
            logger.error(f"TournamentService: Invalid date format in config: {e}")
            return False

    async def update_leaderboard(self):
        logger.info("TournamentService: Updating leaderboard...")
        settings = self.get_settings()
        if not settings:
            return

        try:
            start_time = datetime.strptime(settings["start_time"], "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc)
            end_time = datetime.strptime(settings["end_time"], "%d.%m.%Y %H:%M:%S").replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"TournamentService: Failed to parse dates: {e}")
            return

        # Если турнир еще не начался
        if now < start_time:
            return

        # Если до конца осталось меньше часа, меняем интервал на 60 сек
        time_left = (end_time - now).total_seconds()
        if 0 < time_left <= 3600 and settings.get("check_interval") != 60:
            config = self._load_config()
            config["Tournament"]["Setting"]["check_interval"] = 60
            self._save_config(config)
            logger.info("TournamentService: Changed check_interval to 60s (less than 1 hour left)")

        # Если турнир окончен и призы еще не выданы
        if now > end_time:
            is_distributed = settings.get("is_distributed", False)
            if not is_distributed:
                await self._distribute_prizes(start_time, end_time, settings)
            return

        await self._calculate_and_cache(start_time, end_time, settings)

    async def _calculate_and_cache(self, start_time: datetime, end_time: datetime, settings: dict):
        prizes = self.get_prizes()
        max_place = settings.get("max_place", 50)
        ignore_list = settings.get("ignore_user_id_list", [])

        try:
            async with async_session_factory() as db:
                top_users = await tournament_crud.get_top_users_by_volume(
                    db, start_time, end_time, limit=max_place, ignore_user_ids=ignore_list
                )
                
                prize_catalog_ids = set()
                for k, v in prizes.items():
                    if isinstance(v, dict) and v.get("catalog_id"):
                        try:
                            prize_catalog_ids.add(UUID(v["catalog_id"]))
                        except Exception:
                            pass
                
                prize_images = {}
                if prize_catalog_ids:
                    stmt = select(StickerCatalog).where(StickerCatalog.id.in_(prize_catalog_ids))
                    catalogs = (await db.execute(stmt)).scalars().all()
                    prize_images = {str(c.id): c.image_url for c in catalogs}

                leaderboard = []
                for idx, (user, volume) in enumerate(top_users):
                    place = idx + 1
                    prize_data = prizes.get(str(place), prizes.get("else", {}))
                    prize_cat_id = prize_data.get("catalog_id", "") if isinstance(prize_data, dict) else ""
                    prize_picture_url = prize_images.get(prize_cat_id, "")
                    ton_balance_str = prize_data.get("ton_balance", "") if isinstance(prize_data, dict) else ""

                    leaderboard.append({
                        "place": place,
                        "user_id": str(user.id),
                        "username": user.username,
                        "avatar_url": user.photo_url,
                        "volume": round(float(volume), 2),
                        "prize_picture_url": prize_picture_url,
                        "ton_reward": ton_balance_str
                    })

                now_str = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S")

                # Сохраняем ТОЛЬКО в Redis
                redis_client = await redis_service.connect()
                await redis_client.set(REDIS_KEY, json.dumps({
                    "last_update": now_str,
                    "leaderboard": leaderboard
                }))
                logger.info(f"TournamentService: Leaderboard updated with {len(leaderboard)} players in Redis.")
        except Exception as e:
            logger.error(f"TournamentService: Error calculating leaderboard: {e}")

    async def _distribute_prizes(self, start_time: datetime, end_time: datetime, settings: dict):
        logger.info("TournamentService: Time is up. Distributing prizes...")
        max_place = settings.get("max_place", 50)
        ignore_list = settings.get("ignore_user_id_list", [])
        prizes = self.get_prizes()

        try:
            from backend.models.sticker import UserSticker
            from backend.models.sticker_action import StickerAction
            from backend.models.enums import StickerActionType
            from backend.models.transaction import Transaction
            from backend.models.enums import TransactionType, Currency, TransactionStatus
            
            async with async_session_factory() as db:
                # Финальный пересчет
                top_users = await tournament_crud.get_top_users_by_volume(
                    db, start_time, end_time, limit=max_place, ignore_user_ids=ignore_list
                )
                
                for idx, (user, volume) in enumerate(top_users):
                    place = idx + 1
                    prize_data = prizes.get(str(place), prizes.get("else", {}))
                    pool_id_str = prize_data.get("sticker_pool_id") if isinstance(prize_data, dict) else None
                    ton_balance_str = prize_data.get("ton_balance") if isinstance(prize_data, dict) else None
                    
                    if pool_id_str:
                        try:
                            pool_id = UUID(pool_id_str)
                            # Выдаем стикер
                            stmt = select(UserSticker).where(UserSticker.id == pool_id, UserSticker.owner_id == None)
                            sticker = (await db.execute(stmt)).scalar_one_or_none()
                            
                            if sticker:
                                sticker.owner_id = user.id
                                sticker.is_available = False
                                db.add(sticker)
                                
                                action = StickerAction(
                                    sticker_pool_id=sticker.id,
                                    user_id=user.id,
                                    action_type=StickerActionType.DROP # или создать TOURNAMENT_REWARD
                                )
                                db.add(action)
                                logger.info(f"TournamentService: Assigned prize {pool_id} to user {user.id} (Place {place})")
                            else:
                                logger.warning(f"TournamentService: Prize {pool_id} not available or already claimed")
                        except Exception as e:
                            logger.error(f"TournamentService: Failed to assign prize for place {place}: {e}")
                    
                    if ton_balance_str:
                        try:
                            ton_amount = float(ton_balance_str.replace("+", "").strip())
                            if ton_amount > 0:
                                user.balance_ton = round(user.balance_ton + ton_amount, 9)
                                db.add(user)
                                
                                tx = Transaction(
                                    user_id=user.id,
                                    amount=ton_amount,
                                    currency=Currency.TON,
                                    type=TransactionType.DEPOSIT,
                                    status=TransactionStatus.COMPLETED,
                                    details={"source": "tournament_reward", "place": place}
                                )
                                db.add(tx)
                                logger.info(f"TournamentService: Credited {ton_amount} TON to user {user.id} (Place {place})")
                        except Exception as e:
                            logger.error(f"TournamentService: Failed to parse/credit ton_balance for place {place}: {e}")
                
                await db.commit()

            # Отмечаем как розданное
            config = self._load_config()
            config["Tournament"]["Setting"]["is_distributed"] = True
            self._save_config(config)
            logger.info("TournamentService: Prize distribution complete.")
            
        except Exception as e:
            logger.error(f"TournamentService: Error distributing prizes: {e}")

    async def get_leaderboard_from_cache(self) -> dict:
        try:
            redis_client = await redis_service.connect()
            data = await redis_client.get(REDIS_KEY)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"TournamentService: Redis cache read failed: {e}")
            
        return {"last_update": "", "leaderboard": []}

tournament_service = TournamentService()
    
        