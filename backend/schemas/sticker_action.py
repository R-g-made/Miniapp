from uuid import UUID
from typing import Optional
from datetime import datetime
from backend.schemas.base import BaseSchema

class StickerActionBase(BaseSchema):
    type: str
    user_id: UUID
    user_sticker_id: UUID
    transaction_id: Optional[UUID] = None

class StickerActionRead(StickerActionBase):
    id: UUID
    created_at: datetime

class StickerActionCreate(StickerActionBase):
    pass
