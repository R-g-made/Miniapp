from typing import List, Any
from backend.models.case import Case
from backend.schemas.case import (
    CaseRead, 
    CaseListResponse, 
    CaseCatalogRead, 
    CaseResponse, 
    CaseOpenResponse,
    CaseOpenData
)
from backend.models.enums import Currency
from loguru import logger

class CaseResponseBuilder:
    def __init__(self):
        self._cases: List[Case] = []

    def with_cases(self, cases: List[Case]) -> "CaseResponseBuilder":
        self._cases = cases
        return self

    def with_case(self, case: Case) -> "CaseResponseBuilder":
        self._cases = [case]
        return self

    def build_list(self) -> CaseListResponse:
        return CaseListResponse(
            data=[CaseCatalogRead.model_validate(c, from_attributes=True) for c in self._cases]
        )

    def build_single(self) -> CaseResponse:
        if not self._cases:
             raise ValueError("Case not set")
        
        return CaseResponse(
            data=CaseRead.model_validate(self._cases[0], from_attributes=True)
        )

class CaseOpenBuilder:
    def __init__(self):
        self._drop = None
        self._new_balance = 0.0
        self._currency = Currency.TON

    def with_drop(self, sticker: Any) -> "CaseOpenBuilder":
        """
        Трансформирует UserSticker в StickerMinimal.
        """
        from backend.schemas.sticker import StickerMinimal
        self._drop = StickerMinimal.from_model(sticker)
        return self

    def with_balance(self, balance: float, currency: Currency) -> "CaseOpenBuilder":
        self._new_balance = balance
        self._currency = currency
        return self

    def build(self) -> CaseOpenResponse:
        return CaseOpenResponse(
            data=CaseOpenData(
                drop=self._drop,
                new_balance=self._new_balance,
                currency=self._currency
            )
        )
