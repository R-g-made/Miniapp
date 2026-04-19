from enum import Enum

class Language(str, Enum):
    RU = "ru"
    EN = "en"

class Currency(str, Enum):
    TON = "TON"
    STARS = "STARS"
    NFT = "NFT" #На будующее

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.upper() == value.upper():
                    return member
        return None

class TransactionType(str, Enum):
    DEPOSIT = "DEPOSIT"
    WITHDRAW = "WITHDRAW"
    OPEN_CASE = "OPEN_CASE"
    SELL_STICKER = "SELL_STICKER"
    REFERRAL_REWARD = "REFERRAL_REWARD"
    TRANSFER_OUT = "TRANSFER_OUT"

class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

class ExternalProviderType(str, Enum):
    TON_API = "ton_api"
    GETGEMS = "getgems"
    FRAGMENT = "fragment"
    INTERNAL = "internal"
    THERMOS = "thermos"
    LAFFKA = "laffka"

class StickerActionType(str, Enum):
    DROP = "DROP"
    WITHDRAW = "WITHDRAW"
    SELL_TO_SYSTEM = "SELL_TO_SYSTEM"
    TRANSFER = "TRANSFER"

class WSMessageType(str, Enum):
    LIVE_DROP = "live_drop"
    LIVE_DROP_HISTORY = "live_drop_history"
    GLOBAL_EVENT = "global_event"
    USER_EVENT = "user_event"
    BALANCE_UPDATE = "balance_update"
    CASE_STATUS_UPDATE = "case_status_update"
    ERROR = "error"
    AUTH_SUCCESS = "auth_success"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None
