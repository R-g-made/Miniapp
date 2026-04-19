from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy import String
from backend.models.base import UUIDModel
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.sticker import StickerCatalog
    from backend.models.case import Case
    from backend.models.associations import CaseIssuer

class Issuer(UUIDModel):
    """Эмитенты стикерпаков(Например Goodies, Sticker Store и т.д)"""
    __tablename__ = "issuers"

    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    icon_url: Mapped[str] = mapped_column(String, nullable=True)

    # Relationships
    sticker_catalog: Mapped[List["StickerCatalog"]] = relationship("StickerCatalog", back_populates="issuer")
    case_associations: Mapped[List["CaseIssuer"]] = relationship("CaseIssuer", back_populates="issuer")
    cases: Mapped[List["Case"]] = association_proxy("case_associations", "case")
