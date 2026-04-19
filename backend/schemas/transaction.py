from uuid import UUID
from typing import Optional, Literal
from datetime import datetime
from backend.schemas.base import BaseSchema
from backend.models.enums import Currency, TransactionType, TransactionStatus

class TransactionBase(BaseSchema):
    amount: float
    currency: Currency
    type: TransactionType
    status: TransactionStatus = TransactionStatus.PENDING
    hash: Optional[str] = None

class TransactionRead(TransactionBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

class TransactionCreate(TransactionBase):
    user_id: UUID
