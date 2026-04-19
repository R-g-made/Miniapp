from uuid import UUID
from datetime import datetime
from typing import List, Literal, Optional, Any
from pydantic import BaseModel, Field, computed_field, AliasPath, ConfigDict
from backend.schemas.base import BaseSchema, SuccessResponse
from backend.schemas.issuer import IssuerRead
from backend.schemas.sticker import StickerCatalogRead, StickerMinimal
from backend.models.enums import Currency

# Асоц.схемы

class CaseIssuerCreate(BaseModel):
    issuer_id: UUID
    is_main: bool = False

class CaseIssuerRead(BaseSchema):
    issuer: IssuerRead
    is_main: bool

class CaseItemCreate(BaseModel):
    sticker_catalog_id: UUID
    chance: float = Field(..., ge=0, le=100)

class CaseItemRead(BaseSchema):
    """Схема предмета внутри кейса с плоским маппингом из каталога стикеров"""
    id: UUID
    chance: float = Field(..., ge=0, le=100)
    
    sticker_id: UUID = Field(validation_alias=AliasPath("sticker_catalog", "id"))
    name: str = Field(validation_alias=AliasPath("sticker_catalog", "name"))
    image_url: str = Field(validation_alias=AliasPath("sticker_catalog", "image_url"))
    lottie_url: Optional[str] = Field(default=None, validation_alias=AliasPath("sticker_catalog", "lottie_url"))
    price_ton: Optional[float] = Field(default=None, validation_alias=AliasPath("sticker_catalog", "floor_price_ton"))
    price_stars: Optional[float] = Field(default=None, validation_alias=AliasPath("sticker_catalog", "floor_price_stars"))
    collection_name: Optional[str] = Field(default=None, validation_alias=AliasPath("sticker_catalog", "collection_name"))


class CaseBase(BaseSchema):
    slug: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    image_url: str
    price_ton: float = Field(..., ge=0)
    price_stars: float = Field(..., ge=0)

class CaseCreate(CaseBase):
    is_active: bool = True
    is_chance_distribution: bool = False
    styles: Optional[dict[str, Any]] = None
    issuers: List[CaseIssuerCreate]
    items: List[CaseItemCreate]

class CaseUpdate(BaseModel):
    name: Optional[str] = None
    image_url: Optional[str] = None
    price_ton: Optional[float] = None
    price_stars: Optional[float] = None
    is_active: Optional[bool] = None
    is_chance_distribution: Optional[bool] = None
    styles: Optional[dict[str, Any]] = None
    
    issuers: Optional[List[CaseIssuerCreate]] = None
    items: Optional[List[CaseItemCreate]] = None

class CaseCatalogRead(CaseBase):
    """Схема для списка кейсов (превью)"""
    id: UUID
    styles: Optional[dict[str, Any]] = None

class CaseRead(CaseCatalogRead):
    """Схема для детального вида кейса"""
    items: List[CaseItemRead]

class CaseListResponse(SuccessResponse[List[CaseCatalogRead]]):
    """Список кейсов (превью)"""
    pass

class CaseResponse(SuccessResponse[CaseRead]):
    """Детальный вид кейса"""
    pass

class CaseOpenRequest(BaseSchema):
    currency: Currency

class CaseOpenData(BaseSchema):
    """Данные результата открытия кейса"""
    drop: StickerMinimal
    new_balance: float
    currency: Currency

class CaseOpenResponse(SuccessResponse[CaseOpenData]):
    """Ответ при открытии кейса"""
    pass