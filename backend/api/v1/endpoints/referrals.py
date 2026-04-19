from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from backend.api import deps
from backend.db.session import get_db
from backend.models.user import User
from backend.schemas.referral import ReferralStats, ReferralWithdrawRequest, ReferralStatsResponse, ReferralWithdrawResponse
from backend.crud.referral import referral_repository
from backend.services.referral_service import ReferralService
from backend.core.config import settings
from backend.core.exceptions import EntityNotFound, InvalidOperation, InsufficientFunds

router = APIRouter()

from backend.builders.referral_stats import ReferralStatsBuilder, ReferralWithdrawBuilder

@router.get("/stats", response_model=ReferralStatsResponse)
async def get_referral_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Статистика реферальной программы текущего пользователя.
    """
    logger.debug(f"API: Fetching referral stats for user {current_user.telegram_id}")
    base_stats = await referral_repository.get_stats(db, user_id=current_user.id)
    
    # Используем персональный процент, если он задан, иначе глобальный
    current_ref_rate = current_user.custom_ref_percentage if current_user.custom_ref_percentage is not None else settings.REFERRAL_PERCENTAGE
    
    return (
        ReferralStatsBuilder()
        .with_referral_code(str(current_user.telegram_id))
        .with_ref_percentage(current_ref_rate)
        .with_total_invited(base_stats["total_invited"])
        .with_ton_stats(
            total_earned=base_stats["total_ton"],
            available_balance=current_user.balance_ton
        )
        .with_stars_stats(
            total_earned=base_stats["total_stars"],
            available_balance=current_user.balance_stars,
            locked_balance=base_stats["locked_stars"]
        )
        .build()
    )

@router.post("/withdraw", response_model=ReferralWithdrawResponse)
async def withdraw_referrals(
    obj_in: ReferralWithdrawRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user)
):
    """
    Вывод реферальных вознаграждений в TON.
    Используется последний активный привязанный кошелек пользователя.
    """
    # Проверка привязанного кошелька
    from backend.crud.wallet import wallet_repository
    wallet = await wallet_repository.get_active_by_owner_id(db, owner_id=current_user.id)
    
    if not wallet:
        logger.warning(f"API: Withdrawal failed for user {current_user.telegram_id} - no wallet connected")
        # Фронтенд получит 400 Bad Request с этим сообщением
        raise InvalidOperation("Wallet not connected. Please connect TON wallet first.")

    logger.info(f"API: User {current_user.telegram_id} is requesting referral withdrawal of {obj_in.amount} {obj_in.currency} to linked wallet {wallet.address}")

    if obj_in.currency == Currency.TON:
        referral_service = ReferralService(db)
        result = await referral_service.withdraw_ton(
            user=current_user,
            amount=obj_in.amount,
            address=wallet.address
        )
    else:
        # Для Stars конвертируем в TON и выводим через ReferralService
        referral_service = ReferralService(db)
        # Конвертируем звезды в TON для реальной выплаты
        amount_ton = obj_in.amount * settings.STARS_TO_TON_RATE
        
        result = await referral_service.withdraw_ton(
             user=current_user,
             amount=amount_ton,
             address=current_user.wallet_address,
             is_stars_conversion=True,
             stars_amount=obj_in.amount
         )
        
        if not result:
            raise InsufficientFunds(currency=obj_in.currency.value)
    
    logger.info(f"API: Withdrawal successful for user {current_user.telegram_id}. Result: {result}")
    
    return (
        ReferralWithdrawBuilder()
        .from_result(result)
        .build()
    )
