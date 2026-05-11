from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # DB
    database_url: str = "postgresql+asyncpg://jeontrader:ghtjd12!%40@localhost:5432/jeontrader"

    # Telegram
    telegram_bot_token: str = ""

    # Web
    invite_code: str = "dnt1!"
    secret_key: str = "change-me-in-production"

    # Dev
    allow_outside_hours: bool = False


settings = Settings()
