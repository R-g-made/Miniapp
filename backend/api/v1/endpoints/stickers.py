from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from uuid import UUID
from loguru import logger
from backend.api import deps
from backend.models.user import User
from backend.schemas.sticker import StickerListResponse, StickerTransfer, StickerSellRequest, StickerTransferResponse
from backend.builders.sticker import StickerListBuilder, StickerSellBuilder, StickerTransferBuilder
from backend.crud.sticker import sticker as crud_sticker
from backend.services.sticker_service import sticker_service
from backend.models.enums import Currency

router = APIRouter()

@router.get("/my", response_model=StickerListResponse)
async def get_my_stickers(
    offset: int = 0,
    limit: int = 10,
    issuer_slug: Optional[str] = None,
    current_user: User = Depends(deps.get_current_user),
    db = Depends(deps.get_db)
):
    """
    Инвентарь текущего пользователя
    """
    logger.debug(f"API: Fetching inventory for user {current_user.telegram_id} (offset={offset}, limit={limit}, issuer={issuer_slug})")
    items, total = await crud_sticker.get_user_stickers(
        db=db,
        user_id=current_user.id,
        skip=offset,
        limit=limit,
        issuer_slug=issuer_slug
    )
    
    return (
        StickerListBuilder()
        .with_items(items)
        .with_total(total)
        .build()
    )

from backend.core.exceptions import EntityNotFound, InvalidOperation, InsufficientFunds

@router.post("/{uuid}/sell")
async def sell_sticker(
    uuid: UUID,
    obj_in: StickerSellRequest,
    current_user: User = Depends(deps.get_current_user),
    db = Depends(deps.get_db)
):
    """
    Продать стикер системе за указанную валюту.
    """
    logger.info(f"API: User {current_user.telegram_id} is selling sticker {uuid} for {obj_in.currency}")
    
    sticker, amount, new_balance, used_currency = await sticker_service.sell_sticker(
        db=db,
        sticker_id=uuid,
        user_id=current_user.id,
        currency=obj_in.currency
    )
    
    logger.info(f"API: Sticker {uuid} sold successfully by user {current_user.telegram_id} for {amount} {used_currency}")
    
    return (
        StickerSellBuilder()
        .with_sold_amount(amount)
        .with_currency(used_currency)
        .with_new_balance(new_balance)
        .build()
    )

@router.post("/{uuid}/transfer", response_model=StickerTransferResponse)
async def transfer_sticker(
    uuid: UUID,
    obj_in: StickerTransfer,
    current_user: User = Depends(deps.get_current_user),
    db = Depends(deps.get_db)
):
    """
    Вывод стикера из приложения в кошелек пользователя и Thermos.
    """
    logger.info(f"API: User {current_user.telegram_id} is transferring sticker {uuid}")
    
    success = await sticker_service.transfer(
        db=db,
        sticker_id=uuid,
        user_id=current_user.id
    )
    
    if not success:
        logger.warning(f"API: Failed to initiate transfer for sticker {uuid} by user {current_user.telegram_id}")
        raise InvalidOperation("Failed to initiate transfer")
        
    logger.info(f"API: NFT transfer initiated for sticker {uuid} by user {current_user.telegram_id}")
    
    return (
        StickerTransferBuilder()
        .with_message("NFT transfer initiated")
        .build()
    )
