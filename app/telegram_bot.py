from __future__ import annotations

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes

from app.services.telegram_service import telegram_service


def _chat_id(update: Update) -> str | None:
    return str(update.effective_chat.id) if update.effective_chat else None


async def _get_user(chat_id: str):
    """DB에서 telegram_chat_id로 유저 조회."""
    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_chat_id == chat_id))
        return result.scalar_one_or_none()


async def _save_state(chat_id: str) -> None:
    """메모리 state를 DB에 동기화."""
    from app.registry import get_state
    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select
    state = get_state(chat_id)
    if state is None:
        return
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_chat_id == chat_id))
        user = result.scalar_one_or_none()
        if user:
            user.kis_enabled = state.kis_enabled
            user.kis_split = state.kis_split
            user.kis_buy_count = state.kis_buy_count
            user.kis_position = state.kis_position
            await session.commit()


# ── /start ────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _chat_id(update)
    if not chat_id:
        return

    # 텔레그램 연동 코드 처리: /start XXXXXX
    args = context.args or []
    if args:
        code = args[0]
        from app.db import SessionLocal
        from app.models.user import User
        from app.registry import init_user
        from sqlalchemy import select
        async with SessionLocal() as session:
            result = await session.execute(select(User).where(User.telegram_link_code == code))
            user = result.scalar_one_or_none()
            if user is None:
                await update.message.reply_text("❌ 유효하지 않은 코드입니다.")
                return
            user.telegram_chat_id = chat_id
            user.telegram_link_code = None
            await session.commit()
            await session.refresh(user)
            init_user(chat_id, user)
        await update.message.reply_text("✅ 텔레그램 연동 완료!")
        return

    from app.registry import get_state
    state = get_state(chat_id)
    if state is None:
        await update.message.reply_text("❌ 등록된 계정이 없습니다.\n웹에서 가입 후 연동 코드를 입력하세요.\n예) /start 123456")
        return

    state.kis_enabled = True
    state.kis_split = 1
    state.kis_buy_count = 0
    await _save_state(chat_id)
    await update.message.reply_text("✅ KIS 매매 시작 (1분할, 카운트 리셋)")


# ── /stop ─────────────────────────────────────────────────────────────────────

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _chat_id(update)
    if not chat_id:
        return

    from app.registry import get_state
    state = get_state(chat_id)
    if state is None:
        return

    state.kis_enabled = False
    await _save_state(chat_id)
    await update.message.reply_text("🛑 KIS 매매 중지")


# ── /status ───────────────────────────────────────────────────────────────────

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _chat_id(update)
    if not chat_id:
        return

    from app.registry import get_state, get_kis
    state = get_state(chat_id)
    if state is None:
        await update.message.reply_text("❌ 등록된 계정이 없습니다.")
        return

    kis = get_kis(chat_id)
    pos_text = "없음"
    if kis:
        try:
            from kis.order import get_overseas_balance, get_domestic_balance
            holdings = []
            dom = await get_domestic_balance(kis.auth, kis.account_no)
            for row in dom.get("output1") or []:
                if int(row.get("hldg_qty") or "0") > 0:
                    holdings.append(f"{row['pdno']} {int(row['hldg_qty'])}주")
            ovrs = await get_overseas_balance(kis.auth, kis.account_no, "NASD")
            for row in ovrs.get("output1") or []:
                if int(row.get("ovrs_cblc_qty") or "0") > 0:
                    holdings.append(f"{row['ovrs_pdno']} {int(row['ovrs_cblc_qty'])}주")
            pos_text = "\n  ".join(holdings) if holdings else "없음"
        except Exception as e:
            pos_text = f"조회 실패: {e}"

    await update.message.reply_text(
        "📊 상태\n"
        f"KIS  : {'ON' if state.kis_enabled else 'OFF'}\n"
        f"분할  : {state.kis_split}분할 ({state.kis_buy_count}매수)\n"
        f"최근 시그널: {state.last_signal or '없음'}\n"
        f"실잔고 : {pos_text}"
    )


# ── /balance ──────────────────────────────────────────────────────────────────

async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = _chat_id(update)
    if not chat_id:
        return

    from app.registry import get_kis
    kis = get_kis(chat_id)
    if kis is None:
        await update.message.reply_text("❌ KIS가 연결되지 않았습니다.")
        return

    try:
        from kis.order import get_overseas_balance
        lines = [f"📈 KIS 잔고 (mode={kis.mode})"]

        data = await kis.get_balance()
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

        lines.append("[해외 NASD]")
        overseas_found = False
        try:
            odata = await get_overseas_balance(kis.auth, kis.account_no, "NASD")
            for row in odata.get("output1") or []:
                qty = int(row.get("ovrs_cblc_qty") or "0")
                if qty > 0:
                    ticker = row.get("ovrs_pdno", "")
                    name   = row.get("ovrs_item_name", "")
                    evlu   = row.get("ovrs_stck_evlu_amt", "0")
                    lines.append(f"  {ticker} {name}: {qty}주 / 평가 ${float(evlu):,.2f}")
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
    chat_id = _chat_id(update)
    if not chat_id:
        return

    from app.registry import get_state
    state = get_state(chat_id)
    if state is None:
        return

    args = context.args or []
    if not args or args[0] not in ("1", "2", "4"):
        await update.message.reply_text("사용법: /split 1|2|4")
        return

    n = int(args[0])
    state.kis_split = n
    state.kis_buy_count = 0
    await _save_state(chat_id)
    await update.message.reply_text(f"✅ KIS 분할매수 설정: {n}분할 (카운트 리셋)")


# ── /help ─────────────────────────────────────────────────────────────────────

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 명령어 목록\n"
        "/start        — KIS 매매 시작 (1분할, 카운트 리셋)\n"
        "/start 코드   — 텔레그램 계정 연동\n"
        "/stop         — KIS 매매 중지\n"
        "/status       — 현재 상태 및 포지션 확인\n"
        "/balance      — KIS 잔고 조회 (국내 + 해외)\n"
        "/split 1|2|4  — 분할매수 설정\n"
        "/help         — 이 도움말"
    )


# ── 에러 핸들러 ───────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    from telegram.error import TimedOut, NetworkError
    if isinstance(context.error, (TimedOut, NetworkError)):
        return
    print(f"[TELEGRAM ERROR] {context.error}")


# ── 핸들러 등록 ───────────────────────────────────────────────────────────────

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
