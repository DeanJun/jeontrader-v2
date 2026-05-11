from __future__ import annotations

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # ── Telegram ──────────────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_allowed_chat_id: str = ""

    # ── ngrok ─────────────────────────────────────────────────────────────
    ngrok_public_base_url: str = ""
    ngrok_auth_token: Optional[str] = None

    # ── KIS mode ──────────────────────────────────────────────────────────
    kis_mode: str = "paper"   # "paper" | "real"

    # ── KIS Paper ─────────────────────────────────────────────────────────
    kis_paper_app_key: str = ""
    kis_paper_app_secret: str = ""
    kis_paper_account_no: str = ""

    # ── KIS Real ──────────────────────────────────────────────────────────
    kis_real_app_key: str = ""
    kis_real_app_secret: str = ""
    kis_real_account_no: str = ""

    # ── Dev flags ─────────────────────────────────────────────────────────
    notify_only: bool = False          # True 면 KIS 주문 없이 텔레그램 알림만
    allow_outside_hours: bool = False  # True 면 장외 시간에도 주문 허용

    # ── Derived ───────────────────────────────────────────────────────────
    @property
    def is_paper(self) -> bool:
        return self.kis_mode == "paper"

    @property
    def kis_app_key(self) -> str:
        return self.kis_paper_app_key if self.is_paper else self.kis_real_app_key

    @property
    def kis_app_secret(self) -> str:
        return self.kis_paper_app_secret if self.is_paper else self.kis_real_app_secret

    @property
    def kis_account_no(self) -> str:
        return self.kis_paper_account_no if self.is_paper else self.kis_real_account_no


settings = Settings()
