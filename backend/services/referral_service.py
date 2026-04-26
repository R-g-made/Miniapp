from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from backend.crud.user import user_repository
from backend.crud.referral import referral_repository
from backend.models.user import User
from backend.services.user_service import user_service
from backend.models.referral import Referral
from backend.models.transaction import Transaction
from backend.models.enums import Currency, TransactionType, TransactionStatus
from backend.core.config import settings
from backend.core.exceptions import InsufficientFunds, InvalidOperation, EntityNotFound
import uuid
import asyncio
from loguru import logger

class ReferralService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_referral(self, new_user: User, start_param: str | None) -> None:
        """
        Обрабатывает реферальную ссылку для нового пользователя.
        Если start_param валидный и реферер существует -> создает связь.
        """
        if not start_param:
            logger.debug(f"ReferralService: No start_param for user {new_user.telegram_id}")
            return

        try:
            referrer_telegram_id = int(start_param)
            
            if referrer_telegram_id == new_user.telegram_id:
                logger.warning(f"ReferralService: User {new_user.telegram_id} tried to refer themselves")
                return

            referrer = await user_repository.get_by_telegram_id(self.db, telegram_id=referrer_telegram_id)
            if not referrer:
                logger.warning(f"ReferralService: Referrer with ID {referrer_telegram_id} not found")
                return

            # Check if referral link already exists
            existing_ref = await referral_repository.get_by_referred_id(self.db, referred_id=new_user.id)
            if existing_ref:
                logger.debug(f"ReferralService: User {new_user.telegram_id} already has a referrer")
                return

            # Используем персональный процент реферера, если он задан, иначе глобальный
            ref_percentage = referrer.custom_ref_percentage if referrer.custom_ref_percentage is not None else settings.REFERRAL_PERCENTAGE
            
            await referral_repository.create(
                self.db,
                obj_in={
                    "referrer_id": referrer.id,
                    "referred_id": new_user.id,
                    "ref_percentage": ref_percentage
                },
                commit=True
            )
            logger.info(f"ReferralService: New referral link created: {referrer.telegram_id} -> {new_user.telegram_id} (Rate: {ref_percentage}%)")
            
        except (ValueError, TypeError) as e:
            logger.error(f"ReferralService: Invalid start_param '{start_param}': {e}")
        except Exception as e:
            logger.exception(f"ReferralService: Unexpected error processing referral: {e}")

    async def process_unlocks(self) -> int:
        """
        Перевод заблокированных звезд в доступные по истечении 21 дня.
        Использует транзакции для отслеживания времени начисления.
        """
        from datetime import datetime, timedelta, timezone
        from backend.models.transaction import Transaction, TransactionType, TransactionStatus
        from backend.models.referral import Referral
        from backend.models.user import Currency
        
        # Порог разблокировки - 21 день назад
        # Используем наивное время для сравнения с БД, если там TIMESTAMP WITHOUT TIME ZONE
        now_utc = datetime.now(timezone.utc)
        unlock_threshold = now_utc - timedelta(days=21)
        
        # Находим транзакции реферальных наград в Stars, которые:
        # 1. Старше 21 дня
        # 2. Еще не были разблокированы (нет пометки в details)
        stmt = (
            select(Transaction)
            .where(
                Transaction.type == TransactionType.REFERRAL_REWARD,
                Transaction.currency == Currency.STARS,
                Transaction.status == TransactionStatus.COMPLETED,
                Transaction.created_at <= unlock_threshold.replace(tzinfo=None)
            )
        )
        
        result = await self.db.execute(stmt)
        transactions = result.scalars().all()
        
        unlocked_count = 0
        for tx in transactions:
            # Проверяем, не разблокирована ли уже эта транзакция
            details = tx.details or {}
            if details.get("unlocked"):
                continue
                
            referral_id = details.get("referral_record_id")
            if not referral_id:
                continue
                
            # Получаем запись реферала
            stmt_ref = select(Referral).where(Referral.id = referral_id)
            res_ref = await self.db.execute(stmt_ref)
            ref_record = res_ref.scalar_one_or_none()
            
            if ref_record:
                amount = float(tx.amount)
                
                # Переносим баланс
                if ref_record.reward_stars_locked >= amount:
                    ref_record.reward_stars_locked -= amount
                    ref_record.reward_stars_available += amount
                    
                    # Помечаем транзакцию как разблокированную
                    details["unlocked"] = True
                    details["unlocked_at"] = now_utc.isoformat()
                    tx.details = details
                    
                    self.db.add(ref_record)
                    self.db.add(tx)
                    unlocked_count += 1
                    
        if unlocked_count > 0:
            await self.db.commit()
            logger.info(f"ReferralService: Unlocked {unlocked_count} star rewards")
            
        return unlocked_count
        """
        Вывод реферальных вознаграждений в TON через tonutils.
        """
        logger.info(f"ReferralService: Withdrawal request from user {user_id}: {amount} TON to {address}")

        try:
            # 1. Получаем пользователя с блокировкой
            user = await user_service.get_locked(self.db, user_id)
            if not user:
                raise EntityNotFound("User not found")

            # 2. Проверяем доступный баланс в зависимости от типа
            from backend.crud.referral import referral_repository
            from backend.models.referral import Referral
            
            currency_to_check = "STARS" if is_stars_conversion else "TON"
            available = await referral_repository.get_available_balance(
                self.db, user_id=user.id, currency=currency_to_check
            )
            
            amount_to_check = stars_amount if is_stars_conversion else amount
            if available < amount_to_check:
                logger.warning(f"ReferralService: Insufficient {currency_to_check} balance. Available: {available}, Requested: {amount_to_check}")
                raise InsufficientFunds(currency=currency_to_check)

            # 3. Списываем баланс из реферальных записей
            remaining_to_withdraw = amount_to_check
            reward_attr = Referral.reward_stars_available if is_stars_conversion else Referral.reward_ton
            
            # Проверка минимальной суммы (0.1 TON или 10 Stars)
            min_amount = 100 if is_stars_conversion else 0.1
            if amount_to_check < min_amount:
                logger.warning(f"ReferralService: Withdrawal amount too small. Min: {min_amount}, Requested: {amount_to_check}")
                raise InvalidOperation(f"Minimum withdrawal amount is {min_amount} {currency_to_check}")

            stmt_records = select(Referral).where(Referral.referrer_id == user.id, reward_attr > 0).with_for_update()
            res_records = await self.db.execute(stmt_records)
            referral_records = res_records.scalars().all()
            
            for rec in referral_records:
                if remaining_to_withdraw <= 0:
                    break
                    
                rec_amount = getattr(rec, reward_attr.key)
                if rec_amount >= remaining_to_withdraw:
                    setattr(rec, reward_attr.key, rec_amount - remaining_to_withdraw)
                    remaining_to_withdraw = 0
                else:
                    remaining_to_withdraw -= rec_amount
                    setattr(rec, reward_attr.key, 0.0)
                self.db.add(rec)

            # 4. Выполняем перевод в блокчейне
            from ton_core import to_nano
            from tonutils.clients import TonapiClient
            from tonutils.contracts.wallet import WalletV5R1
            
            # Используем -239 для mainnet и -3 для testnet для корректного subwallet_id
            network_id = -3 if settings.IS_TESTNET else -239
            base_url = "https://testnet.tonapi.io/v2" if settings.IS_TESTNET else "https://tonapi.io/v2"

            client = TonapiClient(
                api_key=settings.TON_API_KEY, 
                network=network_id, 
                base_url=base_url
            )
            await client.connect()
            
            mnemonic_list = settings.NFT_SENDER_MNEMONIC.split()
            if len(mnemonic_list) < 12:
                logger.error("ReferralService: NFT_SENDER_MNEMONIC is too short or missing")
                raise InvalidOperation("Server wallet configuration error")

            wallet, public_key, private_key, mnemonic = WalletV5R1.from_mnemonic(client, mnemonic_list)
            
            logger.debug(f"ReferralService: Server wallet address: {wallet.address.to_str()}")
            
            # Конвертируем TON в нанотоны для блокчейна
            amount_nano = to_nano(amount, 9)
            
            logger.info(f"ReferralService: Initiating real transfer of {amount} TON ({amount_nano} nanoTON) to {address}")
            
            ext_msg = await wallet.transfer(
                destination=address,
                amount=amount_nano,
                body=f"Referral reward for user {user.telegram_id}"
            )
            
            # Получаем хеш транзакции
            if hasattr(ext_msg, "normalized_hash"):
                tx_hash = ext_msg.normalized_hash
            elif hasattr(ext_msg, "hash"):
                tx_hash = ext_msg.hash
            else:
                tx_hash = ext_msg.to_cell().hash.hex()
            
            logger.info(f"ReferralService: Blockchain transfer successful. Hash: {tx_hash}")

            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                currency=Currency.TON,
                type=TransactionType.WITHDRAW,
                status=TransactionStatus.COMPLETED,
                hash=tx_hash,
                details={
                    "target_address": address,
                    "memo": "Referral reward withdrawal",
                    "sender_address": wallet.address.to_str(),
                    "is_stars_conversion": is_stars_conversion,
                    "stars_amount": stars_amount
                }
            )
            
            self.db.add(transaction)
            await self.db.commit()
            
            logger.info(f"ReferralService: Withdrawal completed for {user.telegram_id}. Records updated.")
            
            return {
                "status": "success",
                "transaction_id": str(transaction.id),
                "hash": tx_hash,
                "amount": amount,
                "address": address
            }
            
        except Exception as e:
            logger.error(f"ReferralService: Withdrawal failed for {user.telegram_id}: {str(e)}")
            await self.db.rollback()
            raise InvalidOperation(f"Blockchain transfer failed: {str(e)}")

referral_service = ReferralService
