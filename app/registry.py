from __future__ import annotations

from app.state import AppState
from app.services.kis_service import KISService

# chat_id(str) → AppState
states: dict[str, AppState] = {}

# chat_id(str) → KISService
kis_services: dict[str, KISService] = {}


def get_state(chat_id: str) -> AppState | None:
    return states.get(chat_id)


def get_kis(chat_id: str) -> KISService | None:
    return kis_services.get(chat_id)


def init_user(chat_id: str, user_row) -> None:
    """DB 유저 row로 메모리 state + kis_service 초기화."""
    state = AppState(
        kis_enabled=user_row.kis_enabled,
        kis_split=user_row.kis_split,
        kis_buy_count=user_row.kis_buy_count,
        kis_position=user_row.kis_position or {},
    )
    states[chat_id] = state

    if user_row.kis_app_key and user_row.kis_app_secret and user_row.kis_account_no:
        svc = KISService(
            mode=user_row.kis_mode,
            app_key=user_row.kis_app_key,
            app_secret=user_row.kis_app_secret,
            account_no=user_row.kis_account_no,
        )
        svc.connect()
        kis_services[chat_id] = svc
