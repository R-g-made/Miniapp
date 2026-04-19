from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel
from backend.models.enums import ExternalProviderType

class FloorPriceUpdate(BaseModel):
    catalog_id: UUID
    new_price_ton: Optional[float] = None
    new_price_stars: Optional[float] = None
    details: Dict[str, Any] = {}

class StickerPurchaseRequest(BaseModel):
    catalog_id: UUID
    max_price: float
    max_price_nano: Optional[int] = None # Для точности на границе с блокчейном
    currency: str = "ton"
    details: Dict[str, Any] = {}

class StickerTransferRequest(BaseModel):
    sticker_id: UUID
    target_address: str
    amount_nano: Optional[int] = None # Например для оплаты газа или трансфера
    memo: Optional[str] = None

class ExternalApiResult(BaseModel):
    success: bool
    provider: ExternalProviderType
    details: Dict[str, Any] = {}
    error: Optional[str] = None