from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, BigInteger, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.models.base import UUIDModel
from backend.models.enums import Language
from typing import List, TYPE_CHECKING
import datetime
import uuid

if TYPE_CHECKING:
    from backend.models.sticker import UserSticker
    from backend.models.referral import Referral
    from backend.models.wallet import Wallet
    from backend.models.transaction import Transaction

class User(UUIDModel):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str] = mapped_column(String, nullable=True)
    full_name: Mapped[str] = mapped_column(String, nullable=True)
    photo_url: Mapped[str] = mapped_column(String, nullable=True)
    language_code: Mapped[Language] = mapped_column(String, nullable=True)
    is_premium: Mapped[bool] = mapped_column(default=False)
    
    #Для пуш уведомлений
    allows_write_to_pm: Mapped[bool] = mapped_column(default=False)
    
    # Баланс
    balance_ton: Mapped[float] = mapped_column(Float, default=0.0)
    balance_stars: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Analytics
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_deposit_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    
    total_spent_ton: Mapped[float] = mapped_column(Float, default=0.0)
    total_spent_stars: Mapped[float] = mapped_column(Float, default=0.0)
    total_cases_opened: Mapped[int] = mapped_column(BigInteger, default=0)
    
    # Реферальные настройки
    custom_ref_percentage: Mapped[float] = mapped_column(Float, nullable=True) # Если None - берется глобальный из settings

    # Relationships
    stickers: Mapped[List["UserSticker"]] = relationship("UserSticker", back_populates="owner")
    wallets: Mapped[List["Wallet"]] = relationship("Wallet", back_populates="owner")
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="user")
    
    # Рефералы, которых пригласил этот пользователь
    referrals: Mapped[List["Referral"]] = relationship(
        "Referral", 
        foreign_keys="Referral.referrer_id", 
        back_populates="referrer"
    )
    # Информация о том, кто пригласил этого пользователя
    referred_by: Mapped["Referral"] = relationship(
        "Referral", 
        foreign_keys="Referral.referred_id", 
        back_populates="referred", 
        uselist=False
    )
