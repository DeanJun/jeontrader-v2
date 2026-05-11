from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, Request

from app.services.telegram_service import telegram_service

router = APIRouter()


def _classify(symbol: str) -> str:
    s = symbol.upper()
    if s.isdigit() and len(s) == 6:
        return "kis_domestic"
    return "kis_overseas"


@router.get("/")
def health() -> dict:
    return {"ok": True}


# ── KIS handler ───────────────────────────────────────────────────────────────

async def _handle_kis(chat_id: str, action: str, symbol: str, price: str, exchange: str, notify_only: bool = False) -> dict:
    from app.registry import get_state, get_kis
    from app.telegram_bot import _save_state

    state = get_state(chat_id)
    kis = get_kis(chat_id)

    if state is None or kis is None:
        return {"ok": False, "reason": "user not found or KIS not connected"}

    if not state.kis_enabled:
        await telegram_service.send_message(
            chat_id,
            f"📡 시그널 수신 (KIS OFF)\nAction: {action}\nSymbol: {symbol}\nPrice: {price}"
        )
        return {"ok": True, "traded": False, "reason": "kis disabled"}

    if notify_only:
        await telegram_service.send_message(
            chat_id,
            f"📢 [알림전용] KIS {action}\nSymbol: {symbol}\nPrice: {price}"
        )
        return {"ok": True, "traded": False, "reason": "notify_only"}

    try:
        price_float = float(price)
    except ValueError:
        price_float = 0.0

    if action == "BUY":
        if state.kis_buy_count >= state.kis_split:
            await telegram_service.send_message(
                chat_id,
                f"⏭️ KIS BUY 무시 — 분할매수 완료 ({state.kis_buy_count}/{state.kis_split})\nSymbol: {symbol}"
            )
            return {"ok": True, "traded": False, "reason": "fully invested"}

        remaining_slots = state.kis_split - state.kis_buy_count

        try:
            qty = await kis.calc_buy_qty(symbol, price_float, fraction=1 / remaining_slots)
        except Exception as e:
            await telegram_service.send_message(chat_id, f"❌ KIS 주문가능금액 조회 실패\n{symbol}\n{e}")
            return {"ok": False, "reason": str(e)}

        if qty <= 0:
            await telegram_service.send_message(chat_id, f"⚠️ KIS 잔고 부족 — 매수 불가\nSymbol: {symbol}\nPrice: {price}")
            return {"ok": True, "traded": False, "reason": "insufficient cash"}

        await asyncio.sleep(0.5)

        try:
            await kis.buy(symbol, qty, exchange, price=price_float)
        except Exception as e:
            await telegram_service.send_message(chat_id, f"❌ KIS 매수 실패\n{symbol}\n{e}")
            return {"ok": False, "reason": str(e)}

        state.kis_buy_count += 1
        state.kis_position[symbol] = "long"
        await _save_state(chat_id)
        await telegram_service.send_message(
            chat_id,
            f"✅ KIS 매수 완료 ({state.kis_buy_count}/{state.kis_split})\nSymbol: {symbol}\nQty: {qty}\nPrice: {price}"
        )
        return {"ok": True, "traded": True}

    elif action == "SELL":
        qty = await kis.get_holding_qty(symbol, exchange)
        if qty <= 0:
            state.kis_position[symbol] = None
            state.kis_buy_count = 0
            await _save_state(chat_id)
            await telegram_service.send_message(chat_id, f"⚠️ KIS {symbol} 보유 수량 없음 — 포지션 리셋")
            return {"ok": True, "traded": False, "reason": "no holding"}

        try:
            await kis.sell(symbol, qty, exchange, price=price_float)
        except Exception as e:
            await telegram_service.send_message(chat_id, f"❌ KIS 매도 실패\n{symbol}\n{e}")
            return {"ok": False, "reason": str(e)}

        state.kis_position[symbol] = None
        state.kis_buy_count = 0
        await _save_state(chat_id)
        await telegram_service.send_message(
            chat_id,
            f"✅ KIS 매도 완료\nSymbol: {symbol}\nQty: {qty}\nPrice: {price}"
        )
        return {"ok": True, "traded": True}

    return {"ok": True, "traded": False, "reason": "unknown action"}


# ── Main webhook ──────────────────────────────────────────────────────────────

@router.post("/webhook/{user_id}")
async def tradingview_webhook(user_id: str, request: Request) -> dict:
    try:
        body = await request.body()
        data = await request.json()
    except Exception as e:
        print(f"[WEBHOOK 400] {e}")
        raise HTTPException(status_code=400, detail="invalid json")

    # user_id → DB 조회 → chat_id 확인
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="invalid user_id")

    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="user not found")

    chat_id = user.telegram_chat_id
    if not chat_id:
        raise HTTPException(status_code=400, detail="telegram not linked")

    action  = str(data.get("action", "unknown")).upper()
    symbol  = str(data.get("symbol", "UNKNOWN"))
    price   = str(data.get("price", "N/A"))

    from app.registry import get_state
    state = get_state(chat_id)
    if state:
        state.last_signal = {"action": action, "symbol": symbol, "price": price}

    market = _classify(symbol)
    exchange = "NASD" if market == "kis_overseas" else ""
    print(f"[WEBHOOK] user={user_id} {action} {symbol} @ {price} → {market}")

    return await _handle_kis(chat_id, action, symbol, price, exchange, notify_only=user.notify_only)
