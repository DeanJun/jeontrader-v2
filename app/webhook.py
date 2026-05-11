from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request

from app.state import state
from app.services.telegram_service import telegram_service
from app.services.kis_service import kis_service

router = APIRouter()


def _classify(symbol: str) -> str:
    """심볼 → "kis_domestic" | "kis_overseas" """
    s = symbol.upper()
    if s.isdigit() and len(s) == 6:
        return "kis_domestic"
    return "kis_overseas"


@router.get("/")
def health() -> dict:
    return {
        "ok": True,
        "kis_enabled": state.kis_enabled,
        "last_signal": state.last_signal,
    }


@router.get("/test-telegram")
async def test_telegram() -> dict:
    await telegram_service.send_message("✅ 테스트 메시지 전송 성공")
    return {"ok": True}


# ── KIS handler ───────────────────────────────────────────────────────────────

async def _handle_kis(action: str, symbol: str, price: str, exchange: str = "NASD") -> dict:
    if not state.kis_enabled:
        await telegram_service.send_message(
            f"📡 시그널 수신 (KIS OFF)\nAction: {action}\nSymbol: {symbol}\nPrice: {price}"
        )
        return {"ok": True, "traded": False, "reason": "kis disabled"}

    from app.config import settings
    if settings.notify_only:
        await telegram_service.send_message(
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
                f"⏭️ KIS BUY 무시 — 분할매수 완료 ({state.kis_buy_count}/{state.kis_split})\nSymbol: {symbol}"
            )
            return {"ok": True, "traded": False, "reason": "fully invested"}

        remaining_slots = state.kis_split - state.kis_buy_count

        try:
            qty = await kis_service.calc_buy_qty(symbol, price_float, fraction=1/remaining_slots)
        except Exception as e:
            await telegram_service.send_message(f"❌ KIS 주문가능금액 조회 실패\n{symbol}\n{e}")
            return {"ok": False, "reason": str(e)}

        if qty <= 0:
            await telegram_service.send_message(f"⚠️ KIS 잔고 부족 — 매수 불가\nSymbol: {symbol}\nPrice: {price}")
            return {"ok": True, "traded": False, "reason": "insufficient cash"}

        await asyncio.sleep(0.5)

        try:
            result = await kis_service.buy(symbol, qty, exchange, price=price_float)
        except Exception as e:
            await telegram_service.send_message(f"❌ KIS 매수 실패\n{symbol}\n{e}")
            return {"ok": False, "reason": str(e)}

        state.kis_buy_count += 1
        state.kis_position[symbol] = "long"
        await telegram_service.send_message(
            f"✅ KIS 매수 완료 ({state.kis_buy_count}/{state.kis_split})\nSymbol: {symbol}\nQty: {qty}\nPrice: {price}"
        )
        return {"ok": True, "traded": True}

    elif action == "SELL":
        qty = await kis_service.get_holding_qty(symbol, exchange)
        if qty <= 0:
            state.kis_position[symbol] = None
            state.kis_buy_count = 0
            await telegram_service.send_message(f"⚠️ KIS {symbol} 보유 수량 없음 — 포지션 리셋")
            return {"ok": True, "traded": False, "reason": "no holding"}

        try:
            result = await kis_service.sell(symbol, qty, exchange, price=price_float)
        except Exception as e:
            await telegram_service.send_message(f"❌ KIS 매도 실패\n{symbol}\n{e}")
            return {"ok": False, "reason": str(e)}

        state.kis_position[symbol] = None
        state.kis_buy_count = 0
        await telegram_service.send_message(
            f"✅ KIS 매도 완료\nSymbol: {symbol}\nQty: {qty}\nPrice: {price}"
        )
        return {"ok": True, "traded": True}

    return {"ok": True, "traded": False, "reason": "unknown action"}


# ── Main webhook ──────────────────────────────────────────────────────────────

@router.post("/webhook/tradingview")
async def tradingview_webhook(request: Request) -> dict:
    try:
        body = await request.body()
        print(f"[WEBHOOK RAW] {body}")
        data = await request.json()
    except Exception as e:
        print(f"[WEBHOOK 400] {e} | body={body!r}")
        raise HTTPException(status_code=400, detail="invalid json")

    action  = str(data.get("action", "unknown")).upper()
    symbol  = str(data.get("symbol", "UNKNOWN"))
    price   = str(data.get("price", "N/A"))

    state.last_signal = {"action": action, "symbol": symbol, "price": price}
    market = _classify(symbol)
    print(f"[WEBHOOK] {action} {symbol} @ {price} → {market}")

    exchange = "NASD" if market == "kis_overseas" else ""
    return await _handle_kis(action, symbol, price, exchange)
