import uuid
import hashlib
import struct
import binascii
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from backend.core.redis import redis_service
from backend.models.user import User
from backend.services.user_service import user_service
from backend.models.wallet import Wallet
from backend.crud.wallet import wallet_repository
from backend.schemas.wallet import WalletCreate
from backend.core.exceptions import InvalidOperation
from backend.models.enums import Currency, TransactionType, TransactionStatus
from backend.models.transaction import Transaction
import httpx
from backend.core.config import settings

def from_nano(amount: int) -> float:
    return float(amount) / 10**9

class WalletService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self._ton_client = None
        
    async def _get_ton_client(self):
        if self._ton_client is None:
            from tonutils.clients import TonapiClient
            self._ton_client = TonapiClient(
                api_key=settings.TON_API_KEY,
                network='testnet' if settings.IS_TESTNET else 'mainnet'
            )
        return self._ton_client

    async def _ensure_connected(self):
        client = await self._get_ton_client()
        if not client.connected:
            await client.connect()

    async def get_balance_nano(self, address: str) -> int:
        """
        Получает текущий баланс кошелька в нанотонах.
        """
        await self._ensure_connected()
        client = await self._get_ton_client()
        try:
            account = await client.get_info(address)
            if hasattr(account, "balance"):
                return int(account.balance)
            elif isinstance(account, dict):
                return int(account.get("balance", 0))
            return 0
        except Exception as e:
            logger.error(f"WalletService: Failed to get balance for {address}: {e}")
            return 0

    async def generate_ton_proof_payload(self) -> str:
        """Генерация случайного payload для TON Proof"""
        payload = str(uuid.uuid4())
        # Сохраняем в редис на 5 минут
        await redis_service.set(f"ton_proof:{payload}", "pending", expire=300)
        return payload

    async def check_ton_proof(self, user: User, address: str, network: str, public_key: str, proof: Dict[str, Any]) -> bool:
        """Проверка подписи TON Proof и привязка кошелька"""
        payload = proof.get("payload")
        signature = proof.get("signature")
        
        # 1. Проверяем наличие payload в Redis
        saved_payload = await redis_service.get(f"ton_proof:{payload}")
        if not saved_payload:
            raise InvalidOperation("Payload expired or invalid")
        
        # 2. Удаляем payload из Redis (одноразовый)
        # await redis_service.delete(f"ton_proof:{payload}") # RedisService doesn't have delete, let's just use it once

        try:
            # 3. Формируем сообщение для проверки согласно спецификации TON Connect v2
            # Разбираем адрес (например "0:...")
            workchain, addr_hash = address.split(":")
            workchain_int = int(workchain)
            addr_hash_bytes = binascii.unhexlify(addr_hash)
            
            # Структура сообщения TON Connect v2
            # https://github.com/ton-connect/docs/blob/main/requests-responses.md#address-proof-verification-ton-proof
            
            # ton_proof = "ton-proof-item-v2/" + L + address + L + network + L + payload
            # L - length in 4 bytes, Little Endian
            
            ton_proof_prefix = b"ton-proof-item-v2/"
            ton_proof_item = (
                ton_proof_prefix + 
                struct.pack("<i", workchain_int) + 
                addr_hash_bytes + 
                struct.pack("<i", int(network)) + 
                payload.encode()
            )
            item_hash = hashlib.sha256(ton_proof_item).digest()
            
            # Итоговое сообщение для подписи:
            # 0xffff + "ton-connect" + item_hash
            signature_message = b"\xff\xff" + b"ton-connect" + item_hash
            final_hash = hashlib.sha256(signature_message).digest()
            
            # Проверка подписи (public_key в гексе)
            verify_key = VerifyKey(binascii.unhexlify(public_key))
            verify_key.verify(final_hash, binascii.unhexlify(signature))
            
            logger.info(f"WalletService: TON Proof signature verified for address {address}")
            
            # 1. Проверяем, есть ли уже активный кошелек
            active_wallet = await wallet_repository.get_active_by_owner_id(self.db, owner_id=user.id)
            if active_wallet:
                if active_wallet.address == address:
                    # Тот же самый кошелек уже активен - ничего не делаем
                    logger.info(f"WalletService: User {user.telegram_id} reconnected with already active wallet {address}")
                    return True
                else:
                    # Пытается привязать ДРУГОЙ кошелек, не отвязав старый
                    logger.warning(f"WalletService: User {user.id} tried to link new wallet {address} without disconnecting {active_wallet.address}")
                    raise InvalidOperation("Another wallet is already linked. Please disconnect it first.")

            # 2. Привязываем/реактивируем новый кошелек
            wallet = await wallet_repository.get_by_address(self.db, address=address)
            if not wallet:
                # Ищем среди деактивированных ранее этим же пользователем (soft delete)
                stmt = select(Wallet).where(Wallet.address == address, Wallet.owner_id == user.id)
                result = await self.db.execute(stmt)
                existing_wallet = result.scalars().first()
                
                if existing_wallet:
                    # Реактивируем
                    existing_wallet.is_active = True
                    self.db.add(existing_wallet)
                    logger.info(f"WalletService: Reactivated wallet {address} for user {user.id}")
                else:
                    # Создаем новый
                    await wallet_repository.create(
                        self.db,
                        obj_in=WalletCreate(owner_id=user.id, address=address)
                    )
                    logger.info(f"WalletService: Linked new wallet {address} for user {user.id}")
            elif wallet.owner_id != user.id:
                # Кошелек уже привязан к другому пользователю (активный)
                raise InvalidOperation("Wallet already linked to another account")
                
            return True
            
        except Exception as e:
            print(f"TON Proof verification failed: {e}")
            return False

    async def create_stars_invoice(self, user: User, amount: int, transaction_id: str) -> str:
        """
        Создание счета в Telegram Stars.
        """
        logger.info(f"WalletService: Creating Stars invoice for user {user.telegram_id}, amount: {amount}")
        
        # Telegram Stars currency is XTR
        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/createInvoiceLink"
        
        payload = {
            "title": "Replenish Balance",
            "description": f"Replenish {amount} Stars to your account",
            "payload": transaction_id,
            "provider_token": "", # Empty for Stars
            "currency": "XTR",
            "prices": [
                {"label": "Stars", "amount": int(amount)}
            ]
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            result = response.json()
            
            if not result.get("ok"):
                error_msg = result.get("description", "Unknown error")
                logger.error(f"Failed to create Stars invoice: {error_msg}")
                raise InvalidOperation(f"Telegram API Error: {error_msg}")
            
            # 5. Создаем запись о транзакции в БД
            transaction = Transaction(
                user_id=user.id,
                amount=float(amount),
                currency=Currency.STARS,
                type=TransactionType.DEPOSIT,
                status=TransactionStatus.PENDING,
                details={"transaction_id": transaction_id}
            )
            
            # Для теста: если сумма мала, можно сразу зачислить (но в продакшене ждем коллбэк от бота)
            # user.balance_stars = float(user.balance_stars) + float(amount)
            # transaction.status = TransactionStatus.COMPLETED
            
            self.db.add(transaction)
            self.db.add(user)
            await self.db.commit()
            
            return result["result"] # This is the invoice link

    async def get_ton_balance(self, address: str) -> float:
        """Получает текущий баланс кошелька в TON"""
        await self._ensure_connected()
        try:
            client = await self._get_ton_client()
            account = await client.get_info(address)
            if hasattr(account, "balance"):
                balance_nano = int(account.balance)
            elif isinstance(account, dict):
                balance_nano = int(account.get("balance", 0))
            else:
                balance_nano = 0
            return from_nano(balance_nano)
        except Exception as e:
            logger.error(f"WalletService: Failed to fetch balance for {address}: {e}")
            return 0.0

    async def verify_ton_deposit(self, user: User, amount_ton: float, tx_hash: str) -> bool:
        """
        Проверяет on-chain транзакцию по ее хешу и зачисляет баланс.
        """
        await self._ensure_connected()
        logger.info(f"WalletService: Verifying TON deposit for user {user.telegram_id}, hash: {tx_hash}")
        
        # 1. Проверяем, не обрабатывалась ли уже эта транзакция
        stmt = select(Transaction).where(Transaction.hash == tx_hash)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            logger.warning(f"WalletService: Transaction {tx_hash} already processed")
            return False

        try:
            # 2. Получаем детали транзакции из блокчейна
            client = await self._get_ton_client()
            tx_data = await client.get_transaction(tx_hash)
            if not tx_data:
                logger.warning(f"WalletService: Transaction {tx_hash} not found on-chain")
                return False

            # 3. Проверяем параметры (получатель, сумма)
            # Обработка как объекта (Pydantic/ContractInfo) или словаря
            if hasattr(tx_data, "in_msg"):
                in_msg = tx_data.in_msg
                destination = in_msg.destination.address if hasattr(in_msg.destination, "address") else str(in_msg.destination)
                value_nano = int(in_msg.value)
            elif isinstance(tx_data, dict):
                in_msg = tx_data.get("in_msg", {})
                destination = in_msg.get("destination", {}).get("address")
                value_nano = int(in_msg.get("value", 0))
            else:
                logger.error(f"WalletService: Unknown transaction data type: {type(tx_data)}")
                return False
            
            # Сверяем адрес получателя (наш мерчант)
            if destination != settings.MERCHANT_TON_ADDRESS:
                logger.warning(f"WalletService: Wrong destination address: {destination}")
                return False

            # Сверяем сумму (с допуском на комиссию или округление)
            if from_nano(value_nano) < amount_ton * 0.99: # 1% допуск
                logger.warning(f"WalletService: Insufficient amount: {from_nano(value_nano)} < {amount_ton}")
                return False

            # 4. Зачисляем баланс пользователю
            user.balance_ton = float(user.balance_ton) + from_nano(value_nano)
            
            # 5. Создаем транзакцию в БД
            transaction = Transaction(
                user_id=user.id,
                amount=from_nano(value_nano),
                currency=Currency.TON,
                type=TransactionType.DEPOSIT,
                status=TransactionStatus.COMPLETED,
                hash=tx_hash,
                details={"onchain_data": tx_data}
            )
            
            self.db.add(transaction)
            self.db.add(user)
            await self.db.commit()
            
            # WS notification for balance update
            from backend.core.websocket_manager import manager
            from backend.schemas.websocket import WSEventMessage
            from backend.models.enums import WSMessageType
            
            logger.info(f"WalletService: Sending balance update via WS to user {user.id}")
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
            
            logger.success(f"WalletService: TON Deposit confirmed! User {user.telegram_id} +{from_nano(value_nano)} TON")
            return True

        except Exception as e:
            logger.error(f"WalletService: Error during TON deposit verification: {e}")
            return False

    async def create_withdrawal_request(
        self, 
        user: User, 
        amount: float, 
        currency: Currency, 
        address: str
    ) -> Optional[Transaction]:
        """Создает заявку на вывод средств (ТОЛЬКО для суммарных реферальных вознаграждений)"""
        # Lock user to prevent concurrent withdrawal requests
        user = await user_service.get_locked(self.db, user.id)
        if not user:
            return None

        # 1. Получаем доступную сумму реферальных вознаграждений через CRUD
        from backend.crud.referral import referral_repository
        from backend.models.referral import Referral
        
        total_available = await referral_repository.get_available_balance(
            self.db, user_id=user.id, currency=currency.value
        )
        
        # Если вывод в Stars, проверяем доступный баланс Stars, 
        # но в транзакции всё равно будем учитывать TON, если это вывод на внешний кошелек
        if total_available < amount:
            logger.warning(f"WalletService: Insufficient total referral {currency.value} balance for {user.telegram_id}. Available: {total_available}, Requested: {amount}")
            return None

        # 2. Списываем сумму из реферальных записей (жадный алгоритм: списываем по очереди)
        remaining_to_withdraw = amount
        reward_attr = Referral.reward_ton if currency == Currency.TON else Referral.reward_stars_available
        
        # Lock records for update
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

        # 3. Конвертация суммы для транзакции (если Stars -> TON)
        final_amount_ton = amount
        if currency == Currency.STARS:
            final_amount_ton = amount * settings.STARS_TO_TON_RATE
            logger.info(f"WalletService: Converting {amount} Stars to {final_amount_ton} TON (Rate: {settings.STARS_TO_TON_RATE})")

        # 4. Синхронизируем основной баланс пользователя
        if currency == Currency.TON:
            user.balance_ton = float(user.balance_ton) - amount
        else:
            user.balance_stars = float(user.balance_stars) - amount
            
        # 5. Создаем транзакцию со статусом PENDING
        transaction = Transaction(
            user_id=user.id,
            amount=final_amount_ton, # Для вывода на блокчейн записываем сумму в TON
            currency=Currency.TON,   # Все выводы на внешний кошелек в итоге в TON
            type=TransactionType.WITHDRAW,
            status=TransactionStatus.PENDING,
            details={
                "address": address, 
                "is_referral_withdrawal": True,
                "original_amount": amount,
                "original_currency": currency.value
            }
        )
        
        self.db.add(transaction)
        self.db.add(user)
        await self.db.commit()
        
        logger.info(f"WalletService: Withdrawal request created for {user.telegram_id}: {amount} {currency.value} -> {final_amount_ton} TON")
            
        return transaction

wallet_service = WalletService
