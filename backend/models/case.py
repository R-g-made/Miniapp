from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy import String, Float, ForeignKey, Boolean, Integer, JSON, DateTime
from sqlalchemy.sql import func
from backend.models.base import UUIDModel
import uuid
import datetime
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.sticker import StickerCatalog
    from backend.models.issuer import Issuer
    from backend.models.associations import CaseIssuer, CaseItem

class Case(UUIDModel):
    """Модель кейса"""
    __tablename__ = "cases"

    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    image_url: Mapped[str] = mapped_column(String)

    #стиль для пака(CSS)
    styles: Mapped[dict] = mapped_column(JSON, nullable=True)
    #Пример {"Contain-background-gradient-1color": "red", "Contain-background-gradient-2color": "blue" }
    
    price_ton: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    price_stars: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_chance_distribution: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    issuer_associations: Mapped[List["CaseIssuer"]] = relationship("CaseIssuer", back_populates="case", cascade="all, delete-orphan")
    issuers: Mapped[List["Issuer"]] = association_proxy("issuer_associations", "issuer")
    
    items: Mapped[List["CaseItem"]] = relationship("CaseItem", back_populates="case", cascade="all, delete-orphan")