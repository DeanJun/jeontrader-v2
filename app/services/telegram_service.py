from __future__ import annotations

import asyncio

from telegram.ext import Application

from app.config import settings


class TelegramService:
    def __init__(self) -> None:
        self.app: Application | None = None

    async def start(self) -> None:
        if not settings.telegram_bot_token:
            print("[WARN] TELEGRAM_BOT_TOKEN missing")
            return

        self.app = Application.builder().token(settings.telegram_bot_token).build()

        from app.telegram_bot import setup_telegram_handlers
        await setup_telegram_handlers()

        # 🔥 핵심 추가
        await self.app.initialize()
        await self.app.bot.delete_webhook(drop_pending_updates=True)
        await self.app.bot.get_updates(offset=-1)  # 이전 long-poll 세션 강제 종료
        await asyncio.sleep(1)  # 텔레그램 서버가 이전 세션 끊을 시간
        await self.app.start()
        await self.app.updater.start_polling()

        print("[TELEGRAM] started")

    async def stop(self) -> None:
        if self.app is None:
            return

        try:
            if self.app.updater:
                await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
        except Exception as exc:
            print("[TELEGRAM STOP ERROR]", exc)

    async def send_message(self, text: str) -> None:
        if self.app is None:
            print("[WARN] Telegram app not initialized")
            return

        for attempt in range(3):
            try:
                await self.app.bot.send_message(
                    chat_id=settings.telegram_allowed_chat_id,
                    text=text,
                )
                return
            except Exception as exc:
                if attempt < 2:
                    await asyncio.sleep(1)
                else:
                    print("[TELEGRAM SEND ERROR]", exc)


telegram_service = TelegramService()
