from __future__ import annotations

import random
import string
import uuid

import bcrypt
from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer, BadSignature

from app.config import settings

router = APIRouter()
templates = Jinja2Templates(directory="templates")
_signer = URLSafeSerializer(settings.secret_key, salt="session")

COOKIE = "jt_session"


def _set_session(response: Response, data: dict) -> None:
    response.set_cookie(COOKIE, _signer.dumps(data), httponly=True, samesite="lax")


def _get_session(request: Request) -> dict:
    token = request.cookies.get(COOKIE)
    if not token:
        return {}
    try:
        return _signer.loads(token)
    except BadSignature:
        return {}


def _require_user(request: Request) -> str | None:
    return _get_session(request).get("user_id")


def _r(name: str, request: Request, ctx: dict = {}):
    return templates.TemplateResponse(request, name, ctx)


# ── 로그인 ────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if _require_user(request):
        return RedirectResponse("/dashboard")
    return _r("login.html", request, {"error": None})


@router.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

    if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
        return _r("login.html", request, {"error": "아이디 또는 비밀번호가 올바르지 않습니다."})

    response = RedirectResponse("/dashboard", status_code=303)
    _set_session(response, {"user_id": str(user.id), "invite_ok": True})
    return response


# ── 초대코드 ──────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if _require_user(request):
        return RedirectResponse("/dashboard")
    return RedirectResponse("/login")


@router.get("/invite", response_class=HTMLResponse)
async def invite_get(request: Request):
    return _r("invite.html", request, {"error": None})


@router.post("/invite", response_class=HTMLResponse)
async def invite_post(request: Request, code: str = Form(...)):
    from app.db import SessionLocal
    from app.models.setting import Setting

    async with SessionLocal() as session:
        result = await session.get(Setting, "invite_code")
        invite_code = result.value if result else settings.invite_code

    if code != invite_code:
        return _r("invite.html", request, {"error": "초대코드가 올바르지 않습니다."})
    response = RedirectResponse("/register", status_code=303)
    _set_session(response, {"invite_ok": True})
    return response


# ── 회원가입 ──────────────────────────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    if not _get_session(request).get("invite_ok"):
        return RedirectResponse("/invite")
    error = "이미 사용 중인 아이디입니다." if request.query_params.get("error") == "duplicate" else None
    return _r("register.html", request, {"error": error})


@router.post("/register", response_class=HTMLResponse)
async def register_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    privacy_agree: str = Form(default=""),
):
    if not _get_session(request).get("invite_ok"):
        return RedirectResponse("/invite")

    if not privacy_agree:
        return _r("register.html", request, {"error": "개인정보 수집·이용에 동의해주세요."})
    if password != password_confirm:
        return _r("register.html", request, {"error": "비밀번호가 일치하지 않습니다."})
    if len(password) < 8:
        return _r("register.html", request, {"error": "비밀번호는 8자 이상이어야 합니다."})

    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select

    async with SessionLocal() as session:
        exists = await session.execute(select(User).where(User.username == username))
        if exists.scalar_one_or_none():
            return _r("register.html", request, {"error": "이미 사용 중인 아이디입니다."})

    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    response = RedirectResponse("/kis-setup", status_code=303)
    _set_session(response, {"invite_ok": True, "reg_username": username, "reg_pw_hash": pw_hash, "privacy_agreed": True})
    return response


# ── KIS 연결 테스트 ───────────────────────────────────────────────────────────

@router.post("/kis-test")
async def kis_test(
    request: Request,
    kis_mode: str = Form(...),
    kis_app_key: str = Form(...),
    kis_app_secret: str = Form(...),
):
    from kis.auth import KISAuth
    from fastapi.responses import JSONResponse
    try:
        auth = KISAuth(mode=kis_mode, app_key=kis_app_key, app_secret=kis_app_secret)
        await auth.get_token()
        return JSONResponse({"ok": True, "message": "연결 성공"})
    except Exception as e:
        msg = str(e)
        if "401" in msg:
            msg = "App Key 또는 App Secret이 올바르지 않습니다."
        elif "403" in msg:
            msg = "접근 거부(403) — 모드(모의/실거래)가 키와 일치하는지 확인하세요. 실거래 키는 KIS 홈페이지에서 API 신청 승인 후 사용 가능합니다."
        elif "timeout" in msg.lower():
            msg = "KIS 서버 응답 시간 초과."
        else:
            msg = f"연결 실패: {msg}"
        return JSONResponse({"ok": False, "message": msg})


@router.post("/kis-split")
async def kis_split_set(request: Request):
    from fastapi.responses import JSONResponse
    user_id = _require_user(request)
    if not user_id:
        return JSONResponse({"ok": False})

    body = await request.json()
    n = body.get("split")
    if n not in (1, 2, 4):
        return JSONResponse({"ok": False})

    from app.db import SessionLocal
    from app.models.user import User
    from app.registry import get_state
    from app.telegram_bot import _save_state
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
    if not user or not user.telegram_chat_id:
        return JSONResponse({"ok": False})

    state = get_state(user.telegram_chat_id)
    if state is None:
        return JSONResponse({"ok": False})

    state.kis_split = n
    state.kis_buy_count = 0
    await _save_state(user.telegram_chat_id)
    return JSONResponse({"ok": True})


@router.post("/kis-toggle")
async def kis_toggle(request: Request):
    from fastapi.responses import JSONResponse
    user_id = _require_user(request)
    if not user_id:
        return JSONResponse({"ok": False})

    from app.db import SessionLocal
    from app.models.user import User
    from app.registry import get_state
    from app.telegram_bot import _save_state
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
    if not user or not user.telegram_chat_id:
        return JSONResponse({"ok": False})

    state = get_state(user.telegram_chat_id)
    if state is None:
        return JSONResponse({"ok": False})

    state.kis_enabled = not state.kis_enabled
    await _save_state(user.telegram_chat_id)
    return JSONResponse({"ok": True, "kis_enabled": state.kis_enabled})


@router.post("/kis-test-saved")
async def kis_test_saved(request: Request):
    from kis.auth import KISAuth
    from fastapi.responses import JSONResponse
    user_id = _require_user(request)
    if not user_id:
        return JSONResponse({"ok": False, "message": "로그인 필요"})

    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()

    if not user:
        return JSONResponse({"ok": False, "message": "유저 없음"})
    try:
        auth = KISAuth(mode=user.kis_mode, app_key=user.kis_app_key, app_secret=user.kis_app_secret)
        await auth.get_token()
        return JSONResponse({"ok": True, "message": "연결 성공"})
    except Exception as e:
        msg = str(e)
        if "401" in msg:
            msg = "App Key 또는 App Secret이 올바르지 않습니다."
        elif "403" in msg:
            msg = "접근 거부(403) — 모드(모의/실거래)가 키와 일치하는지 확인하세요. 실거래 키는 KIS 홈페이지에서 API 신청 승인 후 사용 가능합니다."
        elif "timeout" in msg.lower():
            msg = "KIS 서버 응답 시간 초과."
        else:
            msg = f"연결 실패: {msg}"
        return JSONResponse({"ok": False, "message": msg})


# ── KIS 설정 ──────────────────────────────────────────────────────────────────

@router.get("/kis-setup", response_class=HTMLResponse)
async def kis_setup_get(request: Request):
    sess = _get_session(request)
    if not sess.get("user_id") and not sess.get("reg_username"):
        return RedirectResponse("/invite")
    return _r("kis_setup.html", request, {"error": None})


@router.post("/kis-setup", response_class=HTMLResponse)
async def kis_setup_post(
    request: Request,
    kis_mode: str = Form(...),
    kis_customer_id: str = Form(...),
    kis_app_key: str = Form(...),
    kis_app_secret: str = Form(...),
    kis_account_no: str = Form(...),
):
    sess = _get_session(request)
    user_id = sess.get("user_id")
    reg_username = sess.get("reg_username")
    reg_pw_hash = sess.get("reg_pw_hash")

    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select

    link_code = "".join(random.choices(string.digits, k=6))

    async with SessionLocal() as session:
        if user_id:
            # 기존 유저 KIS 정보 수정 (대시보드에서 재설정 시)
            result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
            user = result.scalar_one_or_none()
            if not user:
                return RedirectResponse("/invite")
        elif reg_username and reg_pw_hash:
            # 신규 가입: 이메일 중복 재확인 후 유저 생성
            exists = await session.execute(select(User).where(User.username == reg_username))
            if exists.scalar_one_or_none():
                return RedirectResponse("/register?error=duplicate")
            user = User(username=reg_username, password_hash=reg_pw_hash, privacy_agreed=sess.get("privacy_agreed", False))
            session.add(user)
            await session.flush()
        else:
            return RedirectResponse("/invite")

        user.kis_mode = kis_mode
        user.kis_customer_id = kis_customer_id
        user.kis_app_key = kis_app_key
        user.kis_app_secret = kis_app_secret
        user.kis_account_no = kis_account_no
        user.telegram_link_code = link_code
        await session.commit()
        user_id = str(user.id)

    response = RedirectResponse("/telegram-link", status_code=303)
    _set_session(response, {"user_id": user_id, "invite_ok": True})
    return response


# ── 텔레그램 연동 ─────────────────────────────────────────────────────────────

@router.get("/telegram-link", response_class=HTMLResponse)
async def telegram_link_get(request: Request):
    user_id = _require_user(request)
    if not user_id:
        return RedirectResponse("/invite")

    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()

    if not user:
        return RedirectResponse("/invite")
    if user.telegram_chat_id:
        return RedirectResponse("/dashboard")

    return _r("telegram_link.html", request, {"code": user.telegram_link_code})


@router.get("/telegram-status")
async def telegram_status(request: Request):
    user_id = _require_user(request)
    if not user_id:
        return {"linked": False}

    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()

    return {"linked": bool(user and user.telegram_chat_id)}


@router.post("/telegram-check")
async def telegram_check(request: Request):
    user_id = _require_user(request)
    if not user_id:
        return RedirectResponse("/invite", status_code=303)

    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()

    if user and user.telegram_chat_id:
        return RedirectResponse("/dashboard", status_code=303)
    return RedirectResponse("/telegram-link", status_code=303)


# ── 대시보드 ──────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user_id = _require_user(request)
    if not user_id:
        return RedirectResponse("/invite")

    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()

    if not user:
        return RedirectResponse("/invite")
    if not user.telegram_chat_id:
        return RedirectResponse("/telegram-link")

    from app.registry import get_state
    state = get_state(user.telegram_chat_id)

    return _r("dashboard.html", request, {
        "user_id": user_id,
        "username": user.username,
        "kis_mode": user.kis_mode,
        "kis_enabled": state.kis_enabled if state else False,
        "kis_split": state.kis_split if state else 1,
        "kis_buy_count": state.kis_buy_count if state else 0,
    })


# ── 비밀번호 찾기 (텔레그램으로 임시 비번 전송) ──────────────────────────────

@router.get("/reset-request", response_class=HTMLResponse)
async def reset_request_get(request: Request):
    return _r("reset_request.html", request, {"error": None, "success": False})


@router.post("/reset-request", response_class=HTMLResponse)
async def reset_request_post(request: Request, username: str = Form(...)):
    from app.db import SessionLocal
    from app.models.user import User
    from app.services.telegram_service import telegram_service
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user or not user.telegram_chat_id:
            return _r("reset_request.html", request, {
                "error": "해당 아이디가 없거나 텔레그램 연동이 되어있지 않습니다.",
                "success": False,
            })

        temp_pw = "".join(random.choices(string.ascii_letters + string.digits, k=10))
        user.password_hash = bcrypt.hashpw(temp_pw.encode(), bcrypt.gensalt()).decode()
        await session.commit()

    await telegram_service.send_message(
        user.telegram_chat_id,
        f"🔐 임시 비밀번호가 발급되었습니다.\n\n임시 비번: `{temp_pw}`\n\n로그인 후 반드시 비밀번호를 변경해주세요."
    )
    return _r("reset_request.html", request, {"error": None, "success": True})


# ── 비밀번호 변경 (대시보드에서) ─────────────────────────────────────────────

@router.post("/change-password", response_class=HTMLResponse)
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
):
    user_id = _require_user(request)
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    if new_password != new_password_confirm:
        return RedirectResponse("/dashboard?pw_error=mismatch", status_code=303)
    if len(new_password) < 8:
        return RedirectResponse("/dashboard?pw_error=short", status_code=303)

    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if not user or not bcrypt.checkpw(current_password.encode(), user.password_hash.encode()):
            return RedirectResponse("/dashboard?pw_error=wrong", status_code=303)
        user.password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        await session.commit()

    return RedirectResponse("/dashboard?pw_ok=1", status_code=303)


# ── 어드민 ────────────────────────────────────────────────────────────────────

def _require_admin(request: Request) -> bool:
    user_id = _require_user(request)
    return user_id == settings.admin_user_id if hasattr(settings, "admin_user_id") else False


@router.get("/admin", response_class=HTMLResponse)
async def admin_get(request: Request):
    if not _get_session(request).get("is_admin"):
        return RedirectResponse("/admin-login")

    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).order_by(User.created_at.desc()))
        users = result.scalars().all()

    return _r("admin.html", request, {"users": users, "msg": request.query_params.get("msg")})


@router.get("/admin-login", response_class=HTMLResponse)
async def admin_login_get(request: Request):
    if _get_session(request).get("is_admin"):
        return RedirectResponse("/admin")
    return _r("admin_login.html", request, {"error": None})


@router.post("/admin-login", response_class=HTMLResponse)
async def admin_login_post(
    request: Request,
    password: str = Form(...),
):
    if password != settings.admin_password:
        return _r("admin_login.html", request, {"error": "비밀번호가 올바르지 않습니다."})
    response = RedirectResponse("/admin", status_code=303)
    _set_session(response, {"is_admin": True})
    return response


@router.post("/admin/reset-password")
async def admin_reset_password(request: Request):
    from fastapi.responses import JSONResponse
    if not _get_session(request).get("is_admin"):
        return JSONResponse({"ok": False, "msg": "권한 없음"})

    body = await request.json()
    target_id = body.get("user_id")
    if not target_id:
        return JSONResponse({"ok": False, "msg": "user_id 없음"})

    from app.db import SessionLocal
    from app.models.user import User
    from app.services.telegram_service import telegram_service
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(target_id)))
        user = result.scalar_one_or_none()
        if not user:
            return JSONResponse({"ok": False, "msg": "유저 없음"})

        temp_pw = "".join(random.choices(string.ascii_letters + string.digits, k=10))
        user.password_hash = bcrypt.hashpw(temp_pw.encode(), bcrypt.gensalt()).decode()
        await session.commit()
        chat_id = user.telegram_chat_id
        username = user.username

    if chat_id:
        await telegram_service.send_message(
            chat_id,
            f"🔐 관리자에 의해 비밀번호가 초기화되었습니다.\n\n임시 비번: `{temp_pw}`\n\n로그인 후 반드시 비밀번호를 변경해주세요."
        )
        return JSONResponse({"ok": True, "msg": f"{username} 임시 비번 전송 완료"})
    else:
        return JSONResponse({"ok": True, "msg": f"{username} 임시 비번: {temp_pw} (텔레그램 미연동)"})


@router.post("/admin/toggle-active")
async def admin_toggle_active(request: Request):
    from fastapi.responses import JSONResponse
    if not _get_session(request).get("is_admin"):
        return JSONResponse({"ok": False})

    body = await request.json()
    target_id = body.get("user_id")

    from app.db import SessionLocal
    from app.models.user import User
    from sqlalchemy import select

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(target_id)))
        user = result.scalar_one_or_none()
        if not user:
            return JSONResponse({"ok": False})
        user.is_active = not user.is_active
        await session.commit()
        return JSONResponse({"ok": True, "is_active": user.is_active})


# ── 로그아웃 ──────────────────────────────────────────────────────────────────

@router.get("/logout")
async def logout():
    response = RedirectResponse("/invite", status_code=303)
    response.delete_cookie(COOKIE)
    return response
