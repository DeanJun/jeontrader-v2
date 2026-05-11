from __future__ import annotations

from fastapi import FastAPI

from app.services.telegram_service import telegram_service
from app.services.kis_service import kis_service
from app.webhook import router as webhook_router


def create_app() -> FastAPI:
    app = FastAPI(title="JEONtrader — KIS")

    app.include_router(webhook_router)

    @app.on_event("startup")
    async def on_startup() -> None:
        await telegram_service.start()

        from app.config import settings
        if settings.kis_app_key and settings.kis_app_secret and settings.kis_account_no:
            kis_service.connect()
        else:
            print("[KIS] 키 없음 — KIS 비활성화")
        print("[APP] startup completed")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await telegram_service.stop()
        print("[APP] shutdown completed")

    return app
