from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
import uuid
from backend.api import deps
from backend.db.session import get_db
from backend.models.user import User
from backend.schemas.wallet import (
    WalletReplenishRequest, 
    WalletReplenishResponse, 
    TonProofPayloadResponse, 
    TonProofCheckRequest,
    TonProofCheckResponse,
    WalletDisconnectResponse,
    WalletDisconnectData,
    WalletWithdrawRequest,
    WalletVerifyDepositRequest
)
from backend.services.wallet_service import WalletService
from backend.builders.wallet import WalletReplenishBuilder, TonProofBuilder
from backend.core.config import settings
from backend.models.enums import Currency

router = APIRouter()

@router.get("/ton-proof/payload", response_model=TonProofPayloadResponse)
async def get_ton_proof_payload(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Генерация payload для TON Connect Proof"""
    logger.debug(f"API: Generating TON Proof payload for user {current_user.telegram_id}")
    wallet_service = WalletService(db)
    payload = await wallet_service.generate_ton_proof_payload()
    
    return (
        TonProofBuilder()
        .with_payload(payload)
        .build_payload()
    )

@router.post("/ton-proof/check", response_model=TonProofCheckResponse)
async def check_ton_proof(
    obj_in: TonProofCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """Проверка подписи TON Proof и привязка кошелька"""
    logger.info(f"API: Checking TON Proof for user {current_user.telegram_id} and address {obj_in.address}")
    wallet_service = WalletService(db)
    is_valid = await wallet_service.check_ton_proof(
        user=current_user,
        address=obj_in.address,
        network=obj_in.network,
        public_key=obj_in.public_key,
        proof=obj_in.proof
    )
    
    if not is_valid:
        logger.warning(f"API: Invalid TON Proof signature for user {current_user.telegram_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TON Proof signature"
        )
        
    logger.info(f"API: TON Proof valid, wallet connected for user {current_user.telegram_id}")
    
    return (
        TonProofBuilder()
        .with_address(obj_in.address)
        .build_check()
    )

@router.delete("/disconnect", response_model=WalletDisconnectResponse)
async def disconnect_wallet(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Отвязка (деактивация) активного кошелька пользователя.
    """
    from backend.crud.wallet import wallet_repository
    
    logger.info(f"API: User {current_user.telegram_id} is disconnecting wallet")
    
    success = await wallet_repository.deactivate_active_wallet(db, owner_id=current_user.id)
    await db.commit()
    
    if success:
        logger.debug(f"API: Wallet successfully disconnected for user {current_user.telegram_id}")
    else:
        logger.debug(f"API: No active wallet found to disconnect for user {current_user.telegram_id}")
    
    return WalletDisconnectResponse(
        data=WalletDisconnectData(message="Wallet disconnected successfully")
    )

@router.post("/replenish", response_model=WalletReplenishResponse)
async def replenish_wallet(
    obj_in: WalletReplenishRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Создание заявки на пополнение баланса.
    """
    logger.info(f"API: User {current_user.telegram_id} is replenishing wallet with {obj_in.amount} {obj_in.currency}")
    
    transaction_id = str(uuid.uuid4())
    wallet_service = WalletService(db)
    builder = WalletReplenishBuilder().with_transaction_id(transaction_id)
    
    if obj_in.currency == Currency.TON:
        nanotons = int(obj_in.amount * 10**9)
        
        logger.info(f"API: Generated TON replenishment request for user {current_user.telegram_id}, amount: {nanotons} nanotons")
        
        # Используем ton_core вместо tonutils для формирования BOC
        from ton_core import begin_cell, cell_to_b64, to_nano
        
        # Явно приводим к int, чтобы избежать дробных чисел в строке amount
        nanotons = int(to_nano(obj_in.amount))
        logger.debug(f"API: TON replenishment amount: {nanotons} nanotons, target: {settings.MERCHANT_TON_ADDRESS}")
        
        # Создаем простой текстовый комментарий как Cell
        # В TON Connect комментарий - это Cell с 32-битным префиксом 0 и текстом
        try:
            comment_cell = (
                begin_cell()
                .store_uint(0, 32)
                .store_string(transaction_id)
                .end_cell()
            )
            boc_payload = cell_to_b64(comment_cell)
            logger.debug(f"API: Generated BOC payload: {boc_payload}")
        except Exception as e:
            logger.error(f"API: Failed to generate BOC: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate transaction payload")
        
        return (
            builder
            .with_ton_transaction(
                address=settings.MERCHANT_TON_ADDRESS,
                amount=str(nanotons),
                payload=boc_payload
            )
            .build()
        )
    
    elif obj_in.currency == Currency.STARS:
        payment_url = await wallet_service.create_stars_invoice(
            user=current_user,
            amount=int(obj_in.amount),
            transaction_id=transaction_id
        )
        
        logger.info(f"API: Generated Stars invoice for user {current_user.telegram_id}")
        
        return (
            builder
            .with_payment_url(payment_url)
            .build()
        )
    
    logger.error(f"API: Unsupported currency {obj_in.currency} for user {current_user.telegram_id}")
    raise HTTPException(status_code=400, detail="Unsupported currency")

@router.post("/verify-deposit")
async def verify_deposit(
    obj_in: WalletVerifyDepositRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Проверка пополнения в TON по хешу транзакции или BOC.
    """
    logger.info(f"API: Received verify-deposit request from user {current_user.telegram_id}. Hash: {obj_in.hash}, Has BOC: {bool(obj_in.boc)}")
    wallet_service = WalletService(db)
    
    tx_hash = obj_in.hash
    if not tx_hash and obj_in.boc:
        # Если пришел BOC, пытаемся рассчитать хеш из него
        try:
            from ton_core import Cell
            # Рассчитываем хеш внешнего сообщения из BOC
            tx_hash = Cell.one_from_boc(obj_in.boc).hash.hex()
        except Exception as e:
            logger.error(f"API: Failed to calculate hash from BOC: {e}")
            
    if not tx_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Transaction hash or BOC is required"
        )
        
    success = await wallet_service.verify_ton_deposit(
        user=current_user,
        amount_ton=obj_in.amount,
        tx_hash=tx_hash
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deposit verification failed or transaction not found in blockchain yet"
        )
    
    return {"status": "success", "message": "Deposit verified successfully"}

@router.post("/withdraw")
async def withdraw_funds(
    obj_in: WalletWithdrawRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Заявка на вывод средств (TON или Stars).
    Используется последний активный привязанный кошелек пользователя.
    """
    from backend.crud.wallet import wallet_repository
    wallet = await wallet_repository.get_active_by_owner_id(db, owner_id=current_user.id)
    
    if not wallet:
        logger.warning(f"API: Withdrawal failed for user {current_user.telegram_id} - no wallet connected")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet not connected. Please connect TON wallet first."
        )

    logger.info(f"API: User {current_user.telegram_id} is requesting withdrawal of {obj_in.amount} {obj_in.currency} to linked wallet {wallet.address}")

    wallet_service = WalletService(db)
    transaction = await wallet_service.create_withdrawal_request(
        user=current_user,
        amount=obj_in.amount,
        currency=obj_in.currency,
        address=wallet.address
    )
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient funds"
        )
    
    return {"status": "success", "transaction_id": str(transaction.id)}
