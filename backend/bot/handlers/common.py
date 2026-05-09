from aiogram import Router, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from backend.db.session import async_session_factory
from backend.crud.user import user_repository
from backend.models.transaction import Transaction
from backend.core.websocket_manager import manager
from backend.schemas.websocket import WSEventMessage, WSMessageType
from backend.core.config import settings
from loguru import logger
import contextlib

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """
    Обработчик /start. Отправляет приветственное сообщение с фото и кнопками.
    """
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки только если URL валидны
    if settings.MINI_APP_URL and settings.MINI_APP_URL.startswith("https://"):
        builder.row(types.InlineKeyboardButton(
            text="Open Stickerloot", 
            url=settings.MINI_APP_URL
        ))
    
    if settings.BOT_COMMUNITY_URL and settings.BOT_COMMUNITY_URL.startswith("https://"):
        builder.row(types.InlineKeyboardButton(
            text="Join the Community", 
            url=settings.BOT_COMMUNITY_URL
        ))

    caption = "Welcome to Stickerloot! Open box and collect unique stickers in our mini-app. Start Now!"
    
    await message.answer_photo(
        photo=settings.BOT_START_IMAGE_URL,
        caption=caption,
        reply_markup=builder.as_markup()
    )

@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    payment_info = message.successful_payment
    stars_amount = payment_info.total_amount #
    transaction_hash = payment_info.telegram_payment_charge_id
    
    async with async_session_factory() as db:
        user = await user_repository.get_by_telegram_id(db, telegram_id=message.from_user.id)
        if user:
            new_balance = user.balance_stars + stars_amount
            await user_repository.update(db, db_obj=user, obj_in={"balance_stars": new_balance})
            
            transaction = Transaction(
                user_id=user.id,
                amount=float(stars_amount),
                currency="STARS",
                type="DEPOSIT",
                status="COMPLETED",
                hash=transaction_hash,
                details={"telegram_payment_charge_id": transaction_hash}
            )
            db.add(transaction)
            
            await db.commit()
            
            await manager.send_to_user(
                user_id=str(user.id),
                message=WSEventMessage(
                    type=WSMessageType.BALANCE_UPDATE,
                    data={
                        "currency": "STARS",
                        "new_balance": float(new_balance),
                        "added_amount": float(stars_amount)
                    }
                )
            )
            logger.info(f"Stars Payment: Sent WS balance update to user {user.id}")
        else:
            logger.error(f"Stars Payment: User {message.from_user.id} not found in database.")
