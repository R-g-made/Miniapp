from typing import List, Any, Optional
from backend.builders.base import BaseBuilder
from backend.schemas.sticker import (
    StickerListResponse, 
    StickerListData,
    StickerMinimal, 
    StickerSellResponse, 
    StickerSellData,
    StickerTransferResponse,
    StickerTransferData
)
from backend.models.enums import Currency

class StickerListBuilder(BaseBuilder[StickerListResponse]):
    def _reset(self) -> None:
        self._items: List[StickerMinimal] = []
        self._total: int = 0

    def with_items(self, items: List[Any]) -> "StickerListBuilder":
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        self._items = [StickerMinimal.from_model(item, now=now) for item in items]
        self._total = len(self._items)
        return self

    def with_pagination(self, offset: int, limit: int) -> "StickerListBuilder":
        """Применяет пагинацию к уже загруженному списку"""
        self._items = self._items[offset : offset + limit]
        return self

    def with_total(self, total: int) -> "StickerListBuilder":
        self._total = total
        return self
    
    def only_unlocked(self) -> "StickerListBuilder":
        """Фильтрует только разблокированные стикеры"""
        self._items = [item for item in self._items if not item.is_locked]
        self._total = len(self._items)
        return self

    def only_locked(self) -> "StickerListBuilder":
        """Фильтрует только заблокированные стикеры"""
        self._items = [item for item in self._items if item.is_locked]
        self._total = len(self._items)
        return self

    def only_onchain(self) -> "StickerListBuilder":
        """Фильтрует только on-chain стикеры (NFT)"""
        self._items = [item for item in self._items if item.is_onchain]
        self._total = len(self._items)
        return self

    def only_offchain(self) -> "StickerListBuilder":
        """Фильтрует только off-chain стикеры"""
        self._items = [item for item in self._items if not item.is_onchain]
        self._total = len(self._items)
        return self

    def filter_by_issuer(self, issuer_slug: str) -> "StickerListBuilder":
        """Фильтрует стикеры по эмитенту"""
        self._items = [item for item in self._items if item.issuer_slug == issuer_slug]
        self._total = len(self._items)
        return self

    def sort_by_number(self, reverse: bool = False) -> "StickerListBuilder":
        """Сортирует стикеры по их номеру"""
        self._items.sort(key=lambda x: x.number if x.number is not None else 0, reverse=reverse)
        return self

    def sort_by_price(self, currency: Currency = Currency.TON, reverse: bool = False) -> "StickerListBuilder":
        """Сортирует стикеры по цене флора"""
        if currency == Currency.TON:
            self._items.sort(key=lambda x: x.floor_price_ton or 0, reverse=reverse)
        else:
            self._items.sort(key=lambda x: x.floor_price_stars or 0, reverse=reverse)
        return self

    def build(self) -> StickerListResponse:
        return StickerListResponse(
            data=StickerListData(
                items=self._items,
                total=self._total
            )
        )

class StickerSellBuilder(BaseBuilder[StickerSellResponse]):
    def _reset(self) -> None:
        self._sold_amount: float = 0.0
        self._currency: Currency = Currency.TON
        self._new_balance: float = 0.0

    def with_sold_amount(self, amount: float) -> "StickerSellBuilder":
        self._sold_amount = amount
        return self

    def with_currency(self, currency: Currency) -> "StickerSellBuilder":
        self._currency = currency
        return self

    def with_new_balance(self, balance: float) -> "StickerSellBuilder":
        self._new_balance = balance
        return self

    def build(self) -> StickerSellResponse:
        return StickerSellResponse(
            data=StickerSellData(
                sold_amount=self._sold_amount,
                currency=self._currency,
                new_balance=self._new_balance
            )
        )

class StickerTransferBuilder(BaseBuilder[StickerTransferResponse]):
    def _reset(self) -> None:
        self._message: str = "NFT transfer initiated"
        self._tx_hash: Optional[str] = None

    def with_message(self, message: str) -> "StickerTransferBuilder":
        self._message = message
        return self

    def with_tx_hash(self, tx_hash: Optional[str]) -> "StickerTransferBuilder":
        self._tx_hash = tx_hash
        return self
    
    def from_action(self, action: Any) -> "StickerTransferBuilder":
        """Заполняет данные из модели StickerAction"""
        if hasattr(action, "hash"):
            self._tx_hash = action.hash
        return self

    def build(self) -> StickerTransferResponse:
        return StickerTransferResponse(
            data=StickerTransferData(
                message=self._message,
                tx_hash=self._tx_hash
            )
        )
