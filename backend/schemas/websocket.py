from typing import Any, Optional, Dict
from pydantic import BaseModel
from backend.models.enums import WSMessageType

class WSEventMessage(BaseModel):
    """Единый шаблон сообщения для вс"""
    type: WSMessageType
    event_type: Optional[str] = None
    data: Any
    target_user_id: Optional[str] = None