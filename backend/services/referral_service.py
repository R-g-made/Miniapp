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

    async def withdraw_ton(self, user: User, amount: float, address: str) -> dict:
        """
        Вывод реферальных вознаграждений в TON через tonutils.
        """
        logger.info(f"ReferralService: Withdrawal request from {user.telegram_id}: {amount} TON to {address}")
        
        # Импортируем tonutils только при необходимости
        from tonutils.utils import to_nano, cell_to_hex
        from tonutils.clients import TonapiClient
        from tonutils.contracts.wallet import WalletV5R1
        
        # Lock user for balance update
        user = await user_service.get_locked(self.db, user.id)
        if not user:
            raise EntityNotFound("User not found")
            
        if amount <= 0:
            raise InvalidOperation("Amount must be greater than 0")

        if user.balance_ton < amount:
            logger.warning(f"ReferralService: Insufficient funds for {user.telegram_id}. Has: {user.balance_ton}, Needs: {amount}")
            raise InsufficientFunds(currency="TON")

        try:
            client = TonapiClient(
                api_key=settings.TON_API_KEY, 
                network='testnet' if settings.IS_TESTNET else 'mainnet'
            )
            
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
                tx_hash = cell_to_hex(ext_msg.to_cell().hash)
            
            logger.info(f"ReferralService: Blockchain transfer successful. Hash: {tx_hash}")

            user.balance_ton -= amount
            
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
                    "sender_address": wallet.address.to_str()
                }
            )
            
            self.db.add(user)
            self.db.add(transaction)
            await self.db.commit()
            
            # WS notification for balance update
            from backend.core.websocket_manager import manager
            from backend.schemas.websocket import WSEventMessage, WSMessageType
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
            
            logger.info(f"ReferralService: Withdrawal completed for {user.telegram_id}. New balance: {user.balance_ton}")
            
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
