from uuid import UUID
from typing import Optional
from backend.schemas.base import BaseSchema

class IssuerBase(BaseSchema):
    slug: str
    name: str
    icon_url: Optional[str] = None

class IssuerRead(IssuerBase):
    id: UUID

class IssuerCreate(IssuerBase):
    pass
