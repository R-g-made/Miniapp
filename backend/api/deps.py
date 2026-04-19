from typing import Generator, Optional
from uuid import UUID
from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from backend.core.config import settings
from backend.core.security import security_service
from backend.db.session import get_db
from backend.crud.user import user_repository
from backend.models.user import User
from backend.core.exceptions import EntityNotFound, InvalidToken

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth"
)

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2)
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise InvalidToken("Could not validate credentials")
    except (JWTError, ValidationError, ValueError):
        raise InvalidToken("Could not validate credentials")
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
         raise InvalidToken("Invalid user ID format in token")

    user = await user_repository.get(db, id=user_uuid)
    if not user:
        raise EntityNotFound("User not found")
    return user
