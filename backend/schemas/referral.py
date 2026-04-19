from pydantic import Field
from typing import Literal, Optional
from datetime import datetime
from uuid import UUID
from backend.schemas.base import BaseSchema, SuccessResponse

from backend.models.enums import Currency

class TonStats(BaseSchema):
    total_earned: float = 0.0
    available_balance: float = 0.0

class StarsStats(BaseSchema):
    total_earned: float = 0.0
    locked_balance: float = 0.0
    available_balance: float = 0.0
    available_in_ton: float = 0.0

class ReferralStats(BaseSchema):
    referral_code: str
    ref_percentage: float
    total_invited: int = 0
    ton: TonStats
    stars: StarsStats

class ReferralStatsResponse(SuccessResponse[ReferralStats]):
    pass

class ReferralWithdrawRequest(BaseSchema):
    amount: float = Field(..., gt=0)
    currency: Currency = Currency.TON
    address: Optional[str] = Field(None, min_length=40, max_length=100)

class ReferralWithdrawResponse(SuccessResponse[None]):
    pass
