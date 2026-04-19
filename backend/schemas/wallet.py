from uuid import UUID
from typing import Literal, Optional, List, Dict, Any
from datetime import datetime
from pydantic import Field
from backend.schemas.base import BaseSchema, SuccessResponse
from backend.models.enums import Currency

class WalletBase(BaseSchema):
    address: str
    is_active: bool = True

class WalletRead(WalletBase):
    id: UUID
    owner_id: UUID
    created_at: datetime

class WalletCreate(WalletBase):
    owner_id: UUID

class WalletReplenishRequest(BaseSchema):
    currency: Currency
    amount: float = Field(..., gt=0)

class TonTransactionRequest(BaseSchema):
    address: str = Field(..., min_length=40, max_length=100)
    amount: str = Field(..., min_length=1)
    payload: Optional[str] = None

class TonProofCheckData(BaseSchema):
    address: str

class TonProofCheckResponse(SuccessResponse[TonProofCheckData]):
    pass

class WalletReplenishData(BaseSchema):
    payment_url: Optional[str] = None
    transaction_id: str
    ton_transaction: Optional[TonTransactionRequest] = None

class WalletReplenishResponse(SuccessResponse[WalletReplenishData]):
    pass

class TonProofPayloadData(BaseSchema):
    payload: str

class TonProofPayloadResponse(SuccessResponse[TonProofPayloadData]):
    pass

class TonProofAccount(BaseSchema):
    address: str
    network: str
    publicKey: str
    walletStateInit: str

class TonProofItem(BaseSchema):
    name: str
    payload: str
    signature: str

class TonProofCheckRequest(BaseSchema):
    address: str
    network: str
    public_key: str = Field(..., alias="publicKey")
    proof: Dict[str, Any]

class WalletDisconnectData(BaseSchema):
    message: str

class WalletDisconnectResponse(SuccessResponse[WalletDisconnectData]):
    pass

class WalletWithdrawRequest(BaseSchema):
    currency: Currency
    amount: float = Field(..., gt=0)
    address: Optional[str] = Field(None, min_length=40, max_length=100)

class WalletVerifyDepositRequest(BaseSchema):
    amount: float = Field(..., gt=0)
    hash: str = Field(..., min_length=10)
