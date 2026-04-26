import uuid
import hashlib
import struct
import binascii
import asyncio
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
            
            # В новых версиях tonutils для корректного расчета subwallet_id (особенно V5)
            # нужно передавать network как int: -239 для mainnet, -3 для testnet
            network_id = -3 if settings.IS_TESTNET else -239
            base_url = "https://testnet.tonapi.io/v2" if settings.IS_TESTNET else "https://tonapi.io/v2"
            
            if not settings.TON_API_KEY:
                logger.warning("WalletService: TON_API_KEY is not set. Tonapi requests might fail with 401 Unauthorized.")
            
            self._ton_client = TonapiClient(
                api_key=settings.TON_API_KEY if settings.TON_API_KEY else None, 
                network=network_id, 
                base_url=base_url
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
            
            # 1. Получаем ВСЕ кошельки пользователя (и активные, и нет)
            stmt = select(Wallet).where(Wallet.owner_id == user.id)
            result = await self.db.execute(stmt)
            user_wallets = result.scalars().all()
            
            # 2. Проверяем, привязан ли уже этот адрес к КОМУ-ТО другому (активный)
            other_wallet = await wallet_repository.get_by_address(self.db, address=address)
            if other_wallet and other_wallet.owner_id != user.id:
                raise InvalidOperation("Wallet already linked to another account")

            # 3. Деактивируем все текущие кошельки пользователя, кроме того, который мы сейчас привязываем
            for w in user_wallets:
                if w.address != address and w.is_active:
                    w.is_active = False
                    self.db.add(w)

            # 4. Ищем, есть ли этот адрес уже в списке кошельков пользователя
            target_wallet = next((w for w in user_wallets if w.address == address), None)

            if target_wallet:
                # Если нашли - просто активируем (если был деактивирован)
                if not target_wallet.is_active:
                    target_wallet.is_active = True
                    self.db.add(target_wallet)
                    logger.info(f"WalletService: Reactivated wallet {address} for user {user.id}")
                else:
                    logger.info(f"WalletService: Wallet {address} is already active for user {user.id}")
            else:
                # Если такого адреса у пользователя еще нет - создаем новый
                await wallet_repository.create(
                    self.db,
                    obj_in=WalletCreate(owner_id=user.id, address=address, is_active=True)
                )
                logger.info(f"WalletService: Linked new wallet {address} for user {user.id}")

            await self.db.commit()
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
        Проверяет on-chain транзакцию через события Tonapi и зачисляет баланс.
        """
        logger.info(f"WalletService: Verifying TON deposit for user {user.telegram_id}, hash: {tx_hash}")
        
        # 1. Проверяем, не обрабатывалась ли уже эта транзакция
        stmt = select(Transaction).where(Transaction.hash == tx_hash)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            logger.warning(f"WalletService: Transaction {tx_hash} already processed")
            return False

        try:
            from ton_core import Address
            
            # 2. Получаем детали события напрямую через Tonapi HTTP
            # Мы используем эндпоинт /v2/events/{id}, который принимает и хеш сообщения, и хеш транзакции
            base_url = "https://testnet.tonapi.io/v2" if settings.IS_TESTNET else "https://tonapi.io/v2"
            headers = {}
            if settings.TON_API_KEY:
                headers["Authorization"] = f"Bearer {settings.TON_API_KEY}"
            
            event_data = None
            async with httpx.AsyncClient(timeout=10.0) as http_client:
                # Пытаемся несколько раз, так как индексация может занимать время
                for attempt in range(3):
                    logger.debug(f"WalletService: Attempt {attempt + 1} to find event for hash {tx_hash}")
                    
                    url = f"{base_url}/events/{tx_hash}"
                    try:
                        resp = await http_client.get(url, headers=headers)
                        if resp.status_code == 200:
                            event_data = resp.json()
                            logger.debug(f"WalletService: Found event data")
                            break
                        elif resp.status_code == 404:
                            logger.debug(f"WalletService: Event not found yet (404)")
                        else:
                            logger.debug(f"WalletService: Tonapi error {resp.status_code}: {resp.text}")
                    except Exception as e:
                        logger.debug(f"WalletService: Request error: {e}")
                    
                    if attempt < 2:
                        await asyncio.sleep(1) # Ждем 1 секунду

            if not event_data:
                logger.warning(f"WalletService: Event {tx_hash} not found on-chain after all attempts")
                return False

            # 3. Ищем действие TonTransfer в событии
            found_transfer = False
            actual_value_nano = 0
            
            merchant_addr_hex = Address(settings.MERCHANT_TON_ADDRESS).to_str(is_user_friendly=False)
            
            actions = event_data.get("actions", [])
            for action in actions:
                if action.get("type") == "TonTransfer":
                    # Поле может называться ton_transfer или TonTransfer в зависимости от версии API/прокси
                    transfer = action.get("ton_transfer") or action.get("TonTransfer")
                    if not transfer:
                        continue
                        
                    recipient = transfer.get("recipient", {})
                    recipient_addr = recipient.get("address") if isinstance(recipient, dict) else recipient
                    
                    if not recipient_addr:
                        continue
                        
                    # Нормализуем адрес получателя
                    try:
                        norm_recipient = Address(recipient_addr).to_str(is_user_friendly=False)
                        if norm_recipient == merchant_addr_hex:
                            actual_value_nano = int(transfer.get("amount", 0))
                            # Проверяем сумму (2% допуск)
                            if actual_value_nano >= (amount_ton * 10**9 * 0.98):
                                found_transfer = True
                                logger.info(f"WalletService: Found matching TonTransfer! Amount: {actual_value_nano} nanotons")
                                break
                            else:
                                logger.warning(f"WalletService: Found transfer to merchant but amount mismatch: {actual_value_nano} < {amount_ton * 10**9}")
                    except Exception as e:
                        logger.error(f"WalletService: Error normalizing recipient address {recipient_addr}: {e}")

            if not found_transfer:
                logger.warning(f"WalletService: No matching TonTransfer to merchant {merchant_addr_hex} found in event")
                return False

            # 4. Зачисляем баланс
            actual_ton = from_nano(actual_value_nano)
            user.balance_ton = float(user.balance_ton) + actual_ton
            
            # 5. Создаем транзакцию в БД
            transaction = Transaction(
                user_id=user.id,
                amount=actual_ton,
                currency=Currency.TON,
                type=TransactionType.DEPOSIT,
                status=TransactionStatus.COMPLETED,
                hash=tx_hash,
                details={"onchain_data": str(event_data)}
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
            
            logger.success(f"WalletService: TON Deposit confirmed! User {user.telegram_id} +{actual_ton} TON")
            return True

        except Exception as e:
            logger.error(f"WalletService: Error during TON deposit verification: {e}")
            import traceback
            logger.error(traceback.format_exc())
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
        
        # Проверка минимальной суммы (0.1 TON или 10 Stars)
        min_amount = 10.0 if currency == Currency.STARS else 0.1
        if amount < min_amount:
            logger.warning(f"WalletService: Withdrawal amount too small. Min: {min_amount}, Requested: {amount}")
            return None

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
