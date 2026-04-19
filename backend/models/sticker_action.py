from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, DateTime
from sqlalchemy.sql import func
from backend.models.base import UUIDModel
from backend.models.enums import StickerActionType
import uuid
import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.sticker import UserSticker

class StickerAction(UUIDModel):
    """Аудит действий со стикерами (выпал, выведен, продан системе)"""
    __tablename__ = "sticker_actions"

    sticker_pool_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sticker_pool.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    
    # Виды: DROP, WITHDRAW, SELL_TO_SYSTEM, TRANSFER
    action_type: Mapped[StickerActionType] = mapped_column(String, index=True)
    
    # Блокчейн хэш если есть
    hash: Mapped[str] = mapped_column(String, nullable=True)
    
    # Время создания действия
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    
    # Relationships
    user_sticker: Mapped["UserSticker"] = relationship("UserSticker", back_populates="actions")
