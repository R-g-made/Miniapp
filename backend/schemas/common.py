from typing import Dict, List, Optional, Union
from backend.schemas.base import BaseSchema, SuccessResponse
from backend.schemas.issuer import IssuerRead
from backend.models.enums import Language

class IssuerInfo(BaseSchema):
    name: str
    icon_url: str

class SortingOption(BaseSchema):
    id: str
    label: str

class Dictionaries(BaseSchema):
    issuers: List[IssuerRead]
    sorting_options: List[SortingOption]

class AppConfig(BaseSchema):
    maintenance: bool = False
    min_deposit_amount: float = 1.0
    max_deposit_amount: float = 1000.0

class BootstrapData(BaseSchema):
    dictionaries: Dictionaries
    app_config: AppConfig

class BootstrapResponse(SuccessResponse[BootstrapData]):
    pass
