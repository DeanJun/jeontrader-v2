from __future__ import annotations

import math

from app.config import settings
from kis.auth import KISAuth
from kis.order import (
    place_domestic_order,
    place_overseas_order,
    get_domestic_balance,
    get_overseas_balance,
    get_domestic_orderable_qty,
    get_overseas_available_cash,
)


def _is_domestic(ticker: str) -> bool:
    """6자리 숫자면 국내주식, 아니면 해외주식."""
    return ticker.isdigit() and len(ticker) == 6


class KISService:
    def __init__(self) -> None:
        self._auth: KISAuth | None = None

    def connect(self) -> None:
        self._auth = KISAuth(
            mode=settings.kis_mode,
            app_key=settings.kis_app_key,
            app_secret=settings.kis_app_secret,
        )
        print(f"[KIS] connected (mode={settings.kis_mode})")

    @property
    def auth(self) -> KISAuth:
        if self._auth is None:
            raise RuntimeError("KISService.connect() 를 먼저 호출하세요")
        return self._auth

    async def buy(self, ticker: str, qty: int | float, exchange: str = "NASD", price: float = 0.0) -> dict:
        if _is_domestic(ticker):
            return await place_domestic_order(
                self.auth, settings.kis_account_no, ticker, "buy", int(qty)
            )
        return await place_overseas_order(
            self.auth, settings.kis_account_no, ticker, "buy", qty, exchange, price=price
        )

    async def sell(self, ticker: str, qty: int | float, exchange: str = "NASD", price: float = 0.0) -> dict:
        if _is_domestic(ticker):
            return await place_domestic_order(
                self.auth, settings.kis_account_no, ticker, "sell", int(qty)
            )
        return await place_overseas_order(
            self.auth, settings.kis_account_no, ticker, "sell", qty, exchange, price=price
        )

    async def get_balance(self) -> dict:
        return await get_domestic_balance(self.auth, settings.kis_account_no)

    async def calc_buy_qty(self, ticker: str, price: float, fraction: float = 1.0) -> int | float:
        """주문가능금액 / 현재가. 해외주식은 소수점 2자리, 국내는 정수."""
        if price <= 0:
            return 0
        if _is_domestic(ticker):
            total_qty = await get_domestic_orderable_qty(self.auth, settings.kis_account_no, ticker)
            return math.floor(total_qty * fraction)
        else:
            cash = await get_overseas_available_cash(self.auth, settings.kis_account_no, ticker, price)
            return math.floor(cash * fraction * 0.98 / price)

    async def get_holding_qty(self, ticker: str, exchange: str = "NASD") -> int:
        try:
            if _is_domestic(ticker):
                data = await get_domestic_balance(self.auth, settings.kis_account_no)
                for row in data.get("output1") or []:
                    if row.get("pdno") == ticker:
                        return int(row.get("hldg_qty") or "0")
            else:
                # 해외주식: 여러 거래소에서 찾기
                for exch in [exchange, "NYSE", "AMEX", "NASD"]:
                    try:
                        data = await get_overseas_balance(self.auth, settings.kis_account_no, exch)
                        for row in data.get("output1") or []:
                            if row.get("ovrs_pdno") == ticker:
                                qty = int(row.get("ovrs_cblc_qty") or "0")
                                if qty > 0:
                                    return qty
                    except Exception:
                        continue
        except Exception as e:
            print(f"[KIS] 잔고조회 실패: {e}")
        return 0


kis_service = KISService()
