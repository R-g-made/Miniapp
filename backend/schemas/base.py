from pydantic import BaseModel, field_serializer
from datetime import datetime
from typing import Generic, TypeVar, Optional

T = TypeVar("T")

class BaseSchema(BaseModel):
    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }

    @field_serializer('created_at', 'updated_at', 'last_login_at', 'last_deposit_at', 'sold_at', 'unlock_at', 'unlock_date', check_fields=False)
    def serialize_dt(self, dt: datetime, _info):
        if dt is None:
            return None
        return dt.strftime('%d.%m.%Y %H:%M:%S')

class SuccessResponse(BaseSchema, Generic[T]):
    """Универсальная схема успешного ответа"""
    status: str = "success"
    data: Optional[T] = None
