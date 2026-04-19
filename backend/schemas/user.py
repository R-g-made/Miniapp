from pydantic import BaseModel, Field
from uuid import UUID
from typing import Optional
from datetime import datetime
from backend.schemas.base import BaseSchema, SuccessResponse

class UserBase(BaseSchema):
    telegram_id: int
    username: Optional[str] = None
    full_name: Optional[str] = None
    photo_url: Optional[str] = None
    language_code: Optional[str] = None
    is_premium: bool = False
    allows_write_to_pm: bool = False

class UserCreate(UserBase):
    pass

class UserRead(UserBase):
    id: UUID
    balance_ton: float = Field(..., ge=0)
    balance_stars: float = Field(..., ge=0)
    
    total_spent_ton: float = Field(..., ge=0)
    total_spent_stars: float = Field(..., ge=0)
    
    wallet_address: Optional[str] = None
    custom_ref_percentage: Optional[float] = None

class UserUpdate(BaseModel):
    language_code: Optional[str] = None

class TokenData(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
    ton_proof_payload: Optional[str] = None

class Token(SuccessResponse[TokenData]):
    pass

class UserResponse(SuccessResponse[UserRead]):
    pass

class AuthLogin(BaseModel):
    init_data: str = Field(..., min_length=1)