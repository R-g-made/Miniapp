from typing import Optional, Dict, Any
from backend.schemas.wallet import (
    WalletReplenishResponse, 
    WalletReplenishData,
    TonTransactionRequest, 
    TonProofPayloadResponse,
    TonProofPayloadData,
    TonProofCheckResponse,
    TonProofCheckData
)

class WalletReplenishBuilder:
    def __init__(self):
        self._transaction_id: str = ""
        self._payment_url: Optional[str] = None
        self._ton_transaction: Optional[TonTransactionRequest] = None

    def with_transaction_id(self, transaction_id: str) -> "WalletReplenishBuilder":
        self._transaction_id = transaction_id
        return self

    def with_payment_url(self, payment_url: str) -> "WalletReplenishBuilder":
        self._payment_url = payment_url
        return self

    def with_ton_transaction(self, address: str, amount: str, payload: Optional[str] = None) -> "WalletReplenishBuilder":
        self._ton_transaction = TonTransactionRequest(
            address=address,
            amount=amount,
            payload=payload
        )
        return self

    def build(self) -> WalletReplenishResponse:
        return WalletReplenishResponse(
            data=WalletReplenishData(
                transaction_id=self._transaction_id,
                payment_url=self._payment_url,
                ton_transaction=self._ton_transaction
            )
        )

class TonProofBuilder:
    def __init__(self):
        self._payload: str = ""
        self._address: str = ""

    def with_payload(self, payload: str) -> "TonProofBuilder":
        self._payload = payload
        return self

    def with_address(self, address: str) -> "TonProofBuilder":
        self._address = address
        return self

    def build_payload(self) -> TonProofPayloadResponse:
        return TonProofPayloadResponse(
            data=TonProofPayloadData(payload=self._payload)
        )

    def build_check(self) -> TonProofCheckResponse:
        return TonProofCheckResponse(
            data=TonProofCheckData(address=self._address)
        )
