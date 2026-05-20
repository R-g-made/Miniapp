from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from backend.api import deps
from backend.db.session import get_db
from backend.models.user import User
from backend.schemas.user import UserUpdate, UserResponse
from backend.crud.user import user_repository
from backend.builders.user_profile import UserProfileBuilder

from sqlalchemy.orm import selectinload

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def read_user_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить текущий профиль пользователя.
    """
    logger.debug(f"API: Fetching profile for user {current_user.telegram_id}")
    
    # Подгружаем кошельки для билдера
    from backend.models.user import User
    from sqlalchemy import select
    
    stmt = select(User).options(selectinload(User.wallets)).where(User.id == current_user.id)
    result = await db.execute(stmt)
    user = result.scalar_one()

    return (
        UserProfileBuilder()
        .with_user(user)
        .build()
    )

@router.patch("/me", response_model=UserResponse)
async def update_user_me(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_user),
):
    """
    Обновить текущий профиль пользователя.
    """
    logger.info(f"API: User {current_user.telegram_id} is updating profile: {user_in.model_dump(exclude_unset=True)}")
    user = await user_repository.update(db, db_obj=current_user, obj_in=user_in)
    
    # Подгружаем кошельки после обновления
    stmt = select(User).options(selectinload(User.wallets)).where(User.id == user.id)
    result = await db.execute(stmt)
    user = result.scalar_one()

    return (
        UserProfileBuilder()
        .with_user(user)
        .build()
    )