from __future__ import annotations

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from app.config import settings
from app.state import state
from app.services.telegram_service import telegram_service
from app.services.kis_service import kis_service


def is_allowed(update: Update) -> bool:
    chat_id = update.effective_chat.id if update.effective_chat else None
    return chat_id is not None and str(chat_id) == settings.telegram_allowed_chat_id


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return

    state.kis_enabled = True
    state.kis_split = 1
    state.kis_buy_count = 0
    await update.message.reply_text("✅ KIS 매매 시작 (1분할, 카운트 리셋)")


# ── /stop ─────────────────────────────────────────────────────────────────────

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return

    state.kis_enabled = False
    await update.message.reply_text("🛑 KIS 매매 중지")


# ── /status ───────────────────────────────────────────────────────────────────

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return

    kis_pos = {}
    try:
        from kis.order import get_overseas_balance
        if kis_service._auth is not None:
            # 국내
            data = await kis_service.get_balance()
            for row in data.get("output1") or []:
                qty = int(row.get("hldg_qty") or "0")
                if qty > 0:
                    kis_pos[row.get("pdno", "")] = f"{qty}주"
            # 해외
            for exch in ["NASD", "NYSE", "AMEX"]:
                try:
                    odata = await get_overseas_balance(kis_service.auth, settings.kis_account_no, exch)
                    for row in odata.get("output1") or []:
                        qty = int(row.get("ovrs_cblc_qty") or "0")
                        if qty > 0:
                            kis_pos[row.get("ovrs_pdno", "")] = f"{qty}주"
                except Exception:
                    pass
    except Exception:
        pass

    await update.message.reply_text(
        "📊 상태\n"
        f"KIS  : {'ON' if state.kis_enabled else 'OFF'}\n"
        f"분할  : {state.kis_split}분할 ({state.kis_buy_count}매수)\n"
        f"최근 시그널: {state.last_signal or '없음'}\n"
        f"KIS 포지션 : {kis_pos or '없음'}"
    )


# ── /balance ──────────────────────────────────────────────────────────────────

async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return

    try:
        from kis.order import get_overseas_balance

        lines = [f"📈 KIS 잔고 (mode={settings.kis_mode})"]

        # 국내
        data = await kis_service.get_balance()
        rows = data.get("output1") or []
        output2 = data.get("output2") or [{}]
        total_eval = output2[0].get("tot_evlu_amt", "N/A") if output2 else "N/A"
        lines.append(f"[국내] 총평가: {total_eval}원")
        domestic_found = False
        for row in rows:
            qty = row.get("hldg_qty", "0")
            if int(qty) > 0:
                ticker = row.get("pdno", "")
                name   = row.get("prdt_name", "")
                evlu   = row.get("evlu_amt", "0")
                lines.append(f"  {ticker} {name}: {qty}주 / 평가 {int(evlu):,}원")
                domestic_found = True
        if not domestic_found:
            lines.append("  보유 종목 없음")

        # 해외
        lines.append("[해외]")
        overseas_found = False
        for exch in ["NASD", "NYSE", "AMEX"]:
            try:
                odata = await get_overseas_balance(kis_service.auth, settings.kis_account_no, exch)
                for row in odata.get("output1") or []:
                    qty = int(row.get("ovrs_cblc_qty") or "0")
                    if qty > 0:
                        ticker = row.get("ovrs_pdno", "")
                        name   = row.get("ovrs_item_name", "")
                        evlu   = row.get("ovrs_stck_evlu_amt", "0")
                        lines.append(f"  {ticker} {name} ({exch}): {qty}주 / 평가 ${float(evlu):,.2f}")
                        overseas_found = True
            except Exception:
                pass
        if not overseas_found:
            lines.append("  보유 종목 없음")

        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"❌ KIS 잔고 조회 실패\n{e}")


# ── /split ────────────────────────────────────────────────────────────────────

async def cmd_split(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return

    args = context.args or []
    if not args or args[0] not in ("1", "2", "4"):
        await update.message.reply_text("사용법: /split 1|2|4")
        return

    n = int(args[0])
    state.kis_split = n
    state.kis_buy_count = 0
    await update.message.reply_text(f"✅ KIS 분할매수 설정: {n}분할 (카운트 리셋)")


# ── /help ─────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return

    await update.message.reply_text(
        "📖 명령어 목록\n"
        "/start        — KIS 매매 시작 (1분할, 카운트 리셋)\n"
        "/stop         — KIS 매매 중지\n"
        "/status       — 현재 상태 및 포지션 확인\n"
        "/balance      — KIS 잔고 조회 (국내 + 해외)\n"
        "/split 1|2|4  — 분할매수 설정\n"
        "/help         — 이 도움말"
    )


# ── 핸들러 등록 ───────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram.error import TimedOut, NetworkError
    if isinstance(context.error, (TimedOut, NetworkError)):
        return
    print(f"[TELEGRAM ERROR] {context.error}")


async def setup_telegram_handlers() -> None:
    if telegram_service.app is None:
        return

    telegram_service.app.add_handler(CommandHandler("start",   cmd_start))
    telegram_service.app.add_handler(CommandHandler("stop",    cmd_stop))
    telegram_service.app.add_handler(CommandHandler("status",  cmd_status))
    telegram_service.app.add_handler(CommandHandler("balance", cmd_balance))
    telegram_service.app.add_handler(CommandHandler("split",   cmd_split))
    telegram_service.app.add_handler(CommandHandler("help",    cmd_help))
    telegram_service.app.add_error_handler(error_handler)
