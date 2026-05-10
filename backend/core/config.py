from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "MiniApp"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    
    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""
    DATABASE_URL: Optional[str] = None
    USE_SQLITE: bool = False

    @property
    def async_database_url(self) -> str:
        if self.USE_SQLITE:
            return "sqlite+aiosqlite:///./miniapp.db"
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:5432/{self.POSTGRES_DB}"
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: Optional[str] = None
    USE_REDIS: bool = True

    @property
    def redis_connection_url(self) -> str:
        if self.REDIS_URL:
            return self.REDIS_URL
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # Bot
    BOT_TOKEN: str = ""
    BOT_START_IMAGE_URL: str = "https://i.ibb.co/4w5bdGfW/Sticker-Loot-Icon.png"
    BOT_COMMUNITY_URL: str = "https://t.me/stickerloots"
    MINI_APP_URL: str = "https://t.me/stickerloot_bot/app"
    ADMIN_IDS: list[int] = [] # Список Telegram ID админов для уведомлений
    
    # TON Blockchain
    TON_API_KEY: str = "" # Получи на https://tonconsole.com
    IS_TESTNET: bool = True
    
    # Thermos API
    THERMOS_API_TOKEN: str = ""
    THERMOS_BASE_URL: str = "https://backend.thermos.gifts/api/v1"

    # GetGems API
    GETGEMS_BASE_URL: str = "https://api.getgems.io"
    GETGEMS_API_TOKEN: str = ""
    GETGEMS_API_KEY: str = ""

    # Laffka API
    LAFFKA_BASE_URL: str = "https://laffka-app.shop"
    LAFFKA_INIT_DATA: str = ""
    LAFFKA_REF_CODE: Optional[str] = None
    LAFFKA_API_KEY: str = ""

    # Stickers Tools API
    STICKERS_TOOLS_API_URL: str = "https://stickers.tools/api/stats-new"
    
    # Security
    SECRET_KEY: str = "test-secret-key-for-development-only-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # Business Logic
    REFERRAL_PERCENTAGE: float = 0.05
    MARKET_FEE_PERCENTAGE: float = 0.05 # Комиссия системы (5%)
    STARS_TO_TON_RATE: float = 0.013
    LIVE_DROP_INTERVAL: int = 5 # Интервал генерации дропов в секундах (имитация активности)
    MIN_DEPOSIT: float = 0.1#TODO
    WALLET_ADDRESS: str = "UQDSokuUeDuRCbIKeeCgaiCa001aV0Q3wc6ZX-pdPcnbpNFt"
    
    @property
    def MERCHANT_TON_ADDRESS(self) -> str:
        return self.WALLET_ADDRESS
    
    @property
    def NFT_TON_ADDRESS(self) -> str:
        return self.WALLET_ADDRESS
    
    # Chance Redistribution Settings
    TARGET_RTP: float = 0.90
    CHANCE_BASE_FEE: float = 10.0
    CHANCE_FEE_TOLERANCE: float = 5.0
    CHANCE_CHEAP_THRESHOLD: float = 0.15 # Нижние 15% диапазона цен - дешевые
    CHANCE_EXPENSIVE_THRESHOLD: float = 0.85 # Верхние 15% диапазона цен - дорогие
    CHANCE_CATEGORY_LIMITS: dict = {
        "cheap": {"min": 0.20, "max": 0.95, "weight": 2.0},
        "medium": {"min": 0.05, "max": 0.20, "weight": 0.5},
        "expensive": {"min": 0.0025, "max": 0.05, "weight": 0.05},
    }
    
    # NFT Transfer Settings
    # В проде эти значения ОБЯЗАТЕЛЬНО должны быть в .env
    NFT_SENDER_MNEMONIC: str = ""  # 24 слова от кошелька-отправителя
    NFT_SENDER_WALLET_VERSION: str = "v5r1"
    USE_NFT_2_0: bool = True
    NFT_FUND_ADDRESS: str = "EQDo0y1Ix8Wzqms84bFjL8Vh51RPaEIYwziBBRIi1NMadXui" # Адрес фонда
    NFT_TG_ADDRESS: str = "EQB4ZBNOFNSIpi8Qnikm0M0PE1Hv-D-qi40J_nPyYtzA5SAX" # Адрес ТГ

    # Scheduler Settings (Intervals)
    MAINTENANCE_INTERVAL_HOURS: float = 0.083    # 5 минут для теста (было 6 часов)
    CASE_RECOVERY_INTERVAL_MINUTES: int = 5  # Проверка пустых кейсов
    LIVE_DROP_INTERVAL: int = 5               # Скорость живой ленты (сек)
    
    # Scheduler Settings (Logic)
    MAX_FLOOR_PRICE_CHANGE_PERCENTAGE: Optional[float] = 0.2 
    REFUND_LOOKBACK_DAYS: int = 30
    AUTO_BUY_ENABLED: bool = False
    
    # Disabled Sticker Catalogs for drop (will reroll if selected)
    DISABLED_STICKER_CATALOG_IDS: list[str] = [
        "5cb3182f-9c2e-4dbf-8184-022a11750d42",
        "d3c4b5a6-9f8e-4456-7d6c-5b4a39281706",
        "8e7f6a5b-4c3d-4890-2e1f-0a9b8c7d6e5f"
    ]

    # Disabled Case IDs (will never be active)
    DISABLED_CASE_IDS: list[str] = [
        "0882abc3-e087-443b-a633-0208ee1e93b8"
    ]
    
    # Удаляем старые/дублирующие:
    # AUTO_BUY_INTERVAL_HOURS, FLOOR_CHECK_INTERVAL_HOURS и т.д.
    
    #TODO конкертика
    ANOTHER_SETTING: int = 1
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore"
    }

settings = Settings()