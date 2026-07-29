from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from backend.models.enums import StickerActionType

class DashboardStats(BaseModel):
    total_dropped_items: int
    total_floor_price_ton: float
    total_floor_price_stars: float
    total_spent_ton: float
    total_spent_stars: float
    period_label: str # "Today", "All Time", "2026-06-14"

class DropCard(BaseModel):
    sticker_id: UUID
    image_url: str
    name: str
    player_name: Optional[str]
    price_ton: Optional[float]
    price_stars: Optional[float]
    date: datetime

class DropHistoryResponse(BaseModel):
    items: List[DropCard]
    total: int
    page: int
    size: int

class StickerPoolItem(BaseModel):
    id: UUID
    image_url: str
    name: str
    count_remaining: int
    floor_price_ton: Optional[float]
    floor_price_stars: Optional[float]

class UserAdminInfo(BaseModel):
    id: UUID
    telegram_id: int
    username: Optional[str]
    full_name: Optional[str]
    balance_ton: float
    balance_stars: float

class CaseCreate(BaseModel):
    name: str
    slug: str
    price_ton: float
    price_stars: float
    image_url: str
    item_weights: dict # sticker_catalog_id -> weight
    styles: Optional[dict] = None

class CatalogStickerCreate(BaseModel):
    issuer_id: UUID
    name: str
    collection_name: Optional[str]
    image_url: str
    lottie_url: Optional[str] = None
    is_onchain: bool = False
    collection_address: Optional[str] = None
    priority_market: str = "laffka"
    max_pool_size: int = 100

class BroadcastCreate(BaseModel):
    message: str
    media_url: Optional[str] = None

class AdminLogin(BaseModel):
    password: str
