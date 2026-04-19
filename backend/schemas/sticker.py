from uuid import UUID
from typing import List, Literal, Optional, Any
from datetime import datetime, timezone
from backend.schemas.base import BaseSchema, SuccessResponse
from pydantic import BaseModel, computed_field
from backend.models.enums import Currency
from backend.models.sticker import PriorityMarket

from backend.schemas.issuer import IssuerRead

class StickerCatalogBase(BaseSchema):
    name: str
    collection_name: Optional[str] = None
    image_url: str
    lottie_url: Optional[str] = None
    is_onchain: bool = False
    collection_address: Optional[str] = None
    priority_market: PriorityMarket = PriorityMarket.LAFFKA
    floor_price_ton: Optional[float] = None
    floor_price_stars: Optional[float] = None
    max_pool_size: int = 100

class StickerCatalogRead(StickerCatalogBase):
    id: UUID
    issuer_id: UUID

class StickerCatalogCreate(StickerCatalogBase):
    issuer_id: UUID

class UserStickerBase(BaseSchema):
    is_available: bool = False
    is_onchain: bool = False
    ton_price: Optional[float] = None
    stars_price: Optional[int] = None

class UserStickerRead(UserStickerBase):
    id: UUID
    catalog: StickerCatalogRead
    owner_id: Optional[UUID] = None
    number: int
    created_at: datetime

from backend.core.config import settings

class StickerMinimal(BaseSchema):
    """
    Универсальная облегченная схема для стикера.
    Используется везде: инвентарь, открытие кейса, Live Drop.
    """
    id: UUID
    number: Optional[int] = None
    name: str
    image_url: str
    lottie_url: Optional[str] = None
    floor_price_ton: Optional[float] = None
    floor_price_stars: Optional[float] = None
    issuer_slug: str
    unlock_date: Optional[datetime] = None
    is_locked: bool = False
    is_onchain: bool = False

    @staticmethod
    def from_model(item: Any, now: Optional[datetime] = None) -> "StickerMinimal":
        """
        Фабричный метод для создания схемы из модели UserSticker.
        Централизует логику расчета цен и проверок блокировок.
        """
        catalog = getattr(item, "catalog", None)
        if not catalog:
            return StickerMinimal(
                id=item.id,
                name="Unknown Sticker",
                image_url="",
                issuer_slug="unknown"
            )

        fee_multiplier = 1.0 - settings.MARKET_FEE_PERCENTAGE
        
        ton_net = None
        if catalog.floor_price_ton is not None:
            ton_net = catalog.floor_price_ton * fee_multiplier
            
        stars_net = None
        if catalog.floor_price_stars is not None:
            stars_net = catalog.floor_price_stars * fee_multiplier
        
        is_locked = False
        if not now:
            now = datetime.now(timezone.utc)
            
        if item.unlock_date:
            # Приводим к timezone-aware для корректного сравнения
            unlock_date = item.unlock_date
            if unlock_date.tzinfo is None:
                unlock_date = unlock_date.replace(tzinfo=timezone.utc)
            
            if unlock_date > now:
                is_locked = True
            
        return StickerMinimal(
            id=item.id,
            number=item.number,
            name=catalog.name,
            image_url=catalog.image_url,
            lottie_url=catalog.lottie_url,
            floor_price_ton=ton_net,
            floor_price_stars=stars_net,
            issuer_slug=catalog.issuer.slug if catalog.issuer else "unknown",
            unlock_date=item.unlock_date,
            is_locked=is_locked,
            is_onchain=item.is_onchain
        )

class StickerListData(BaseSchema):
    items: List[StickerMinimal]
    total: int

class StickerListResponse(SuccessResponse[StickerListData]):
    pass

class StickerSellData(BaseSchema):
    sold_amount: float
    currency: Currency
    new_balance: float

class StickerSellResponse(SuccessResponse[StickerSellData]):
    pass

class StickerSellRequest(BaseModel):
    currency: Currency

class StickerTransfer(BaseModel):
    target_wallet: Optional[str] = None
    currency: Currency = Currency.TON

class StickerTransferData(BaseSchema):
    message: str
    tx_hash: Optional[str] = None

class StickerTransferResponse(SuccessResponse[StickerTransferData]):
    pass
