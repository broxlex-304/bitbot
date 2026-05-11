from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Exchange
    exchange_id: str = "mexc"
    api_key: str = ""
    api_secret: str = ""

    # Trading
    default_symbol: str = "BTC/USDT"
    default_timeframe: str = "15m"
    trade_amount_usdt: float = 10.0
    max_open_trades: int = 3
    confidence_threshold: float = 85.0
    stop_loss_percent: float = 2.0
    take_profit_percent: float = 4.0

    # News APIs
    newsapi_key: Optional[str] = None
    cryptopanic_key: Optional[str] = None

    # App
    secret_key: str = "change-this-secret"
    debug: bool = True
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
