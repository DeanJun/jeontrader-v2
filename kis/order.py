from __future__ import annotations

from kis.auth import KISAuth


def _split(account_no: str) -> tuple[str, str]:
    return account_no.split("-", 1)


async def place_domestic_order(
    auth: KISAuth,
    account_no: str,
    ticker: str,
    action: str,          # "buy" | "sell"
    qty: int,
    order_type: str = "market",
    price: float = 0.0,
) -> dict:
    token = await auth.get_token()
    cano, prdt = _split(account_no)

    if auth.mode == "paper":
        tr_id = "VTTC0802U" if action == "buy" else "VTTC0801U"
    else:
        tr_id = "TTTC0802U" if action == "buy" else "TTTC0801U"

    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "PDNO": ticker,
        "ORD_DVSN": "01" if order_type == "market" else "00",
        "ORD_QTY": str(qty),
        "ORD_UNPR": "0" if order_type == "market" else str(int(price)),
    }

    print(f"[KIS] 국내 {action} {ticker} x{qty} (mode={auth.mode})")

    resp = await auth.client.post(
        f"{auth.base_url}/uapi/domestic-stock/v1/trading/order-cash",
        headers=auth.build_headers(tr_id, token),
        json=body,
    )
    data = resp.json()

    if data.get("rt_cd") != "0":
        raise RuntimeError(f"KIS 국내주문 오류: {data.get('msg1', data)}")

    print(f"[KIS] 국내주문 완료 odno={data.get('output', {}).get('ODNO', 'N/A')}")
    return data


async def place_overseas_order(
    auth: KISAuth,
    account_no: str,
    ticker: str,
    action: str,
    qty: int | float,
    exchange: str = "NASD",   # NASD | NYSE | AMEX
    order_type: str = "market",
    price: float = 0.0,
) -> dict:
    token = await auth.get_token()
    cano, prdt = _split(account_no)

    if auth.mode == "paper":
        tr_id = "VTTT1002U" if action == "buy" else "VTTT1001U"
    else:
        tr_id = "TTTT1002U" if action == "buy" else "TTTT1006U"

    body = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "OVRS_EXCG_CD": exchange,
        "PDNO": ticker,
        "ORD_QTY": str(int(qty)) if qty == int(qty) else f"{qty:.2f}",
        "OVRS_ORD_UNPR": str(price),
        "ORD_SVR_DVSN_CD": "0",
        "ORD_DVSN": "00",
    }

    print(f"[KIS] 해외 {action} {ticker} x{qty} @ {price} {exchange} (mode={auth.mode})")

    resp = await auth.client.post(
        f"{auth.base_url}/uapi/overseas-stock/v1/trading/order",
        headers=auth.build_headers(tr_id, token),
        json=body,
    )
    data = resp.json()

    if data.get("rt_cd") != "0":
        raise RuntimeError(f"KIS 해외주문 오류: {data.get('msg1', data)}")

    print(f"[KIS] 해외주문 완료 odno={data.get('output', {}).get('ODNO', 'N/A')}")
    return data


async def get_domestic_orderable_qty(auth: KISAuth, account_no: str, ticker: str) -> int:
    """국내주식 시장가 주문가능수량 조회 (KIS가 현재가 기준으로 계산한 값)."""
    token = await auth.get_token()
    cano, prdt = _split(account_no)

    tr_id = "VTTC8908R" if auth.mode == "paper" else "TTTC8908R"

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "PDNO": ticker,
        "ORD_UNPR": "0",
        "ORD_DVSN": "01",
        "CMA_EVLU_AMT_ICLD_YN": "Y",
        "OVRS_ICLD_YN": "N",
    }

    resp = await auth.client.get(
        f"{auth.base_url}/uapi/domestic-stock/v1/trading/inquire-psbl-order",
        headers=auth.build_headers(tr_id, token),
        params=params,
    )
    data = resp.json()

    if data.get("rt_cd") != "0":
        raise RuntimeError(f"KIS 주문가능금액 조회 오류: {data.get('msg1', data)}")

    qty = data.get("output", {}).get("nrcvb_buy_qty", "0")
    return int(qty)


async def get_overseas_available_cash(
    auth: KISAuth, account_no: str, ticker: str = "", price: float = 0.0
) -> int:
    """해외주식 매수가능금액 조회 (원화 환산)."""
    token = await auth.get_token()
    cano, prdt = _split(account_no)

    tr_id = "VTTS3007R" if auth.mode == "paper" else "TTTS3007R"

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "OVRS_EXCG_CD": "NASD",
        "OVRS_ORD_UNPR": str(price),
        "ITEM_CD": ticker,
    }

    resp = await auth.client.get(
        f"{auth.base_url}/uapi/overseas-stock/v1/trading/inquire-psamount",
        headers=auth.build_headers(tr_id, token),
        params=params,
    )
    data = resp.json()

    if data.get("rt_cd") != "0":
        raise RuntimeError(f"KIS 해외주문가능금액 조회 오류: {data.get('msg1', data)}")

    amt = data.get("output", {}).get("frcr_ord_psbl_amt1", "0")
    return int(float(amt))


async def get_overseas_balance(
    auth: KISAuth,
    account_no: str,
    exchange: str = "NASD",
    currency: str = "USD",
) -> dict:
    """해외주식 잔고 조회."""
    token = await auth.get_token()
    cano, prdt = _split(account_no)

    tr_id = "VTTS3012R" if auth.mode == "paper" else "TTTS3012R"

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "OVRS_EXCG_CD": exchange,
        "TR_CRCY_CD": currency,
        "CTX_AREA_FK200": "",
        "CTX_AREA_NK200": "",
    }

    resp = await auth.client.get(
        f"{auth.base_url}/uapi/overseas-stock/v1/trading/inquire-balance",
        headers=auth.build_headers(tr_id, token),
        params=params,
    )
    data = resp.json()

    if data.get("rt_cd") != "0":
        raise RuntimeError(f"KIS 해외잔고조회 오류: {data.get('msg1', data)}")

    return data


async def get_domestic_balance(auth: KISAuth, account_no: str) -> dict:
    token = await auth.get_token()
    cano, prdt = _split(account_no)

    tr_id = "VTTC8434R" if auth.mode == "paper" else "TTTC8434R"

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": prdt,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "01",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }

    resp = await auth.client.get(
        f"{auth.base_url}/uapi/domestic-stock/v1/trading/inquire-balance",
        headers=auth.build_headers(tr_id, token),
        params=params,
    )
    data = resp.json()

    if data.get("rt_cd") != "0":
        raise RuntimeError(f"KIS 잔고조회 오류: {data.get('msg1', data)}")

    return data
