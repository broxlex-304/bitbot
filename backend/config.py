from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # Exchange
    exchange_id: str = "mexc"
    api_key: str = ""
    api_secret: str = ""

    # Trading
    symbol: str = "BTC/USDT"
    timeframe: str = "15m"
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

    # Telegram Alerts
    telegram_token: str = "8309156047:AAEapWWNwWQY_vcnYXaMoblyXxLph8qk_UA"
    telegram_chat_id: str = "1788255388"
    
    # Database
    database_url: str = "sqlite:///bitbot.db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
