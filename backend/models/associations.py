from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Boolean, Float
from backend.models.base import Base, UUIDModel
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.case import Case
    from backend.models.issuer import Issuer
    from backend.models.sticker import StickerCatalog

class CaseIssuer(Base):
    __tablename__ = "case_issuers"

    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"), primary_key=True)
    issuer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("issuers.id"), primary_key=True)
    
    is_main: Mapped[bool] = mapped_column(Boolean, default=False) # Главный эмитент

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="issuer_associations")
    issuer: Mapped["Issuer"] = relationship("Issuer", back_populates="case_associations")

class CaseItem(UUIDModel):
    """Связь кейса и его содержимого с указанием шанса выпадения"""
    __tablename__ = "case_items"

    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id"), index=True)
    sticker_catalog_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sticker_catalog.id"), index=True)
    
    chance: Mapped[float] = mapped_column(Float) # Например, 0.05 для 5%
    
    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="items")
    sticker_catalog: Mapped["StickerCatalog"] = relationship("StickerCatalog", back_populates="case_items")