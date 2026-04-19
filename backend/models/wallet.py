from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Boolean, DateTime
from sqlalchemy.sql import func
from backend.models.base import UUIDModel
import uuid
import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.user import User

class Wallet(UUIDModel):
    """Крипто-кошельки пользователей (TON)"""
    __tablename__ = "wallets"

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    address: Mapped[str] = mapped_column(String, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    
    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="wallets")
