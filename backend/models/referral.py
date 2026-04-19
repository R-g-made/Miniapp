from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, DateTime, Float, Integer
from sqlalchemy.sql import func
from backend.models.base import UUIDModel
import uuid
import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.user import User

class Referral(UUIDModel):
    """Статистика реферальной связи и доступные награды"""
    __tablename__ = "referrals"

    # Кто пригласил
    referrer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    # Кого пригласили
    referred_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    # Статистика реферала
    ref_percentage: Mapped[float] = mapped_column(Float, default=0.05) # По умолчанию 5%
    
    # Награды в TON 
    reward_ton: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Награды в Stars 
    reward_stars_locked: Mapped[float] = mapped_column(Float, default=0.0)
    reward_stars_available: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Время создания и обновления
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    referrer: Mapped["User"] = relationship("User", foreign_keys=[referrer_id], back_populates="referrals")
    referred: Mapped["User"] = relationship("User", foreign_keys=[referred_id], back_populates="referred_by")
