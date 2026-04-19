from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Float, Boolean, ForeignKey, DateTime, Integer, Enum
from sqlalchemy.sql import func
from backend.models.base import UUIDModel
import uuid
import datetime
import enum
from typing import List, TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from backend.models.user import User
    from backend.models.issuer import Issuer
    from backend.models.associations import CaseItem
    from backend.models.sticker_action import StickerAction

class PriorityMarket(str, enum.Enum):
    LAFFKA = "laffka"
    GETGEMS = "getgems"
    THERMOS = "thermos"

class StickerCatalog(UUIDModel):
    """Метаданные стикера"""
    __tablename__ = "sticker_catalog"

    issuer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("issuers.id"), index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    collection_name: Mapped[str] = mapped_column(String, nullable=True)
    image_url: Mapped[str] = mapped_column(String)
    lottie_url: Mapped[str] = mapped_column(String, nullable=True)
    
    # Если ончейн (по умолчанию для новых экземпляров)
    is_onchain: Mapped[bool] = mapped_column(Boolean, default=False)
    collection_address: Mapped[str] = mapped_column(String, nullable=True)
    
    # Приоритетный маркет для автобая
    priority_market: Mapped[str] = mapped_column(
        String, 
        default=PriorityMarket.LAFFKA.value,
        server_default=PriorityMarket.LAFFKA.value
    )
    
    # Флоровая цена
    floor_price_ton: Mapped[float] = mapped_column(Float, nullable=True)
    floor_price_stars: Mapped[float] = mapped_column(Float, nullable=True)

    # Прочее
    max_pool_size: Mapped[int] = mapped_column(Integer, default=100) # Максимально допустимое количество в пуле
    last_inventory_check: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True) # Время последней проверки инвентаря
    

    # Relationships
    issuer: Mapped["Issuer"] = relationship("Issuer", back_populates="sticker_catalog")
    instances: Mapped[List["UserSticker"]] = relationship("UserSticker", back_populates="catalog")
    case_items: Mapped[List["CaseItem"]] = relationship("CaseItem", back_populates="sticker_catalog")

class UserSticker(UUIDModel):
    """Информация о конкретном экземпляре стикера"""
    __tablename__ = "sticker_pool"

    catalog_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sticker_catalog.id"), index=True)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    number: Mapped[int] = mapped_column(Integer, index=True)
 
    # Если принадлежит системе (доступен для выпадения)
    is_available: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Флаг ончейн для конкретного экземпляра
    is_onchain: Mapped[bool] = mapped_column(Boolean, default=False)
    
    ton_price: Mapped[float] = mapped_column(Float, nullable=True)
    stars_price: Mapped[int] = mapped_column(Integer, nullable=True)

    unlock_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    
    # Onchain info
    nft_address: Mapped[str] = mapped_column(String, nullable=True, index=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    catalog: Mapped["StickerCatalog"] = relationship("StickerCatalog", back_populates="instances")
    owner: Mapped["User"] = relationship("User", back_populates="stickers")
    actions: Mapped[List["StickerAction"]] = relationship("StickerAction", back_populates="user_sticker")

class ThermosMapping(UUIDModel):
    """Таблица соответствия наших стикеров с ID в API Thermos"""
    __tablename__ = "thermos_mappings"

    catalog_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sticker_catalog.id"), unique=True, index=True)

    thermos_collection_id: Mapped[int] = mapped_column(Integer, index=True)
    thermos_character_id: Mapped[int] = mapped_column(Integer, index=True)
    
    thermos_collection_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    thermos_character_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    catalog: Mapped["StickerCatalog"] = relationship("StickerCatalog")

class LaffkaMapping(UUIDModel):
    """Таблица соответствия наших стикеров с ID в API Laffka"""
    __tablename__ = "laffka_mappings"

    catalog_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sticker_catalog.id"), unique=True, index=True)

    # Формат 'collection_id:sticker_id' для поиска в Laffka
    laffka_sticker_id: Mapped[str] = mapped_column(String, index=True)
    
    # Дополнительные метаданные Laffka
    laffka_collection_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    laffka_collection_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    laffka_sticker_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    catalog: Mapped["StickerCatalog"] = relationship("StickerCatalog")
