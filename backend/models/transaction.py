from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from backend.models.base import UUIDModel
from backend.models.enums import Currency, TransactionType, TransactionStatus
import uuid
import datetime
from typing import TYPE_CHECKING
from backend.models.enums import Currency

if TYPE_CHECKING:
    from backend.models.user import User

class Transaction(UUIDModel):
    """Финансовых транзакций (Stars, TON)"""
    __tablename__ = "transactions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    
    # Финансовая информация
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[Currency] = mapped_column(String)  # Currency.TON or Currency.STARS
    
    # Types: DEPOSIT, WITHDRAW, PURCHASE_CASE, SELL_STICKER, REFERRAL_REWARD
    type: Mapped[TransactionType] = mapped_column(String, index=True)
    status: Mapped[TransactionStatus] = mapped_column(String, default=TransactionStatus.PENDING, index=True) # PENDING, COMPLETED, FAILED
    
    # Безопасность
    #TODO логика безопасности и отслеживания транзакций
    # Для Stars это transaction_id от TG, для TON это hash транзакции
    hash: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=True)
    
    # Дополнительная информация о транзакции (JSON)
    details: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    #Время создания транзакции
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="transactions")
