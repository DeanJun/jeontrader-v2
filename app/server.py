from __future__ import annotations

from fastapi import FastAPI

from fastapi.staticfiles import StaticFiles

from app.services.telegram_service import telegram_service
from app.webhook import router as webhook_router
from app.web import router as web_router


def create_app() -> FastAPI:
    app = FastAPI(title="JEONtrader v2")

    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(web_router)
    app.include_router(webhook_router)

    @app.on_event("startup")
    async def on_startup() -> None:
        # DB에서 활성 유저 로드 → 메모리 state 초기화
        await _load_users()

        # 텔레그램 봇 시작
        await telegram_service.start()
        print("[APP] startup completed")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        await telegram_service.stop()
        print("[APP] shutdown completed")

    return app


async def _load_users() -> None:
    """서버 시작 시 DB의 활성 유저를 메모리에 올림."""
    from app.db import SessionLocal
    from app.models.user import User
    from app.registry import init_user
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.is_active == True, User.telegram_chat_id != None)
        )
        users = result.scalars().all()

    for user in users:
        init_user(user.telegram_chat_id, user)

    print(f"[APP] {len(users)}명 유저 로드 완료")
