from typing import Dict, List, Any
from backend.schemas.common import (
    BootstrapResponse, 
    BootstrapData,
    SortingOption, 
    AppConfig, 
    Dictionaries
)
from backend.models.issuer import Issuer

from backend.schemas.issuer import IssuerRead

class BootstrapBuilder:
    def __init__(self):
        self._issuers: List[IssuerRead] = []
        self._sorting_options: List[SortingOption] = []
        self._app_config = AppConfig()

    def with_issuers(self, issuers: List[Issuer]):
        self._issuers = [IssuerRead.model_validate(issuer) for issuer in issuers]
        return self

    def with_sorting_options(self, options: List[Dict[str, Any]]):
        self._sorting_options = [SortingOption(**opt) for opt in options]
        return self

    def with_config(self, maintenance: bool = False, min_deposit: float = 1.0):
        self._app_config = AppConfig(
            maintenance=maintenance,
            min_deposit_amount=min_deposit
        )
        return self

    def build(self) -> BootstrapResponse:
        return BootstrapResponse(
            data=BootstrapData(
                dictionaries=Dictionaries(
                    issuers=self._issuers,
                    sorting_options=self._sorting_options
                ),
                app_config=self._app_config
            )
        )