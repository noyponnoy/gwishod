from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

import bcrypt
import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from pydantic import BaseModel
from .config import (
    JWT_ALGORITHM,
    JWT_EXPIRE_DAYS,
    JWT_SECRET,
    TELEGRAM_ADMIN_IDS,
    TELEGRAM_BOT_TOKEN,
    _hash_password,
    _load_admins,
    _save_admins,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
COOKIE_NAME = "gw_panel_token"

# Макс. возраст initData WebApp (секунды)
TG_INIT_DATA_MAX_AGE = 86400


class LoginRequest(BaseModel):
    username: str
    password: str


class AdminInfo(BaseModel):
    username: str


class AddAdminRequest(BaseModel):
    username: str
    password: str


class TelegramWebAppLoginRequest(BaseModel):
    """initData из window.Telegram.WebApp.initData"""
    init_data: str


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _find_admin(username: str) -> Optional[dict]:
    for a in _load_admins():
        if a.get("username") == username:
            return a
    return None


def _create_token(username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=JWT_EXPIRE_DAYS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def _is_tg_panel_user(username: str) -> bool:
    """Сессия tg:123456 — если ID в списке TG-админов."""
    if not username.startswith("tg:"):
        return False
    raw = username[3:]
    if not raw.isdigit():
        return False
    return int(raw) in TELEGRAM_ADMIN_IDS


def get_current_user(token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME)) -> str:
    username = _decode_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован",
        )
    # Обычный админ панели (логин/пароль)
    if _find_admin(username) is not None:
        return username
    # Вход через Telegram WebApp
    if _is_tg_panel_user(username):
        return username
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не авторизован",
    )


def _set_auth_cookie(resp, token: str, request: Request) -> None:
    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    # path="/" — cookie видна и под /adminka-android-api/
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=JWT_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=is_https,
        samesite="lax",
        path="/",
    )


def _validate_telegram_webapp_init_data(init_data: str) -> Optional[dict]:
    """Проверка подписи Telegram WebApp initData (HMAC-SHA256).

    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN не задан — WebApp login отключён")
        return None
    if not init_data or not init_data.strip():
        return None

    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    except Exception:
        return None

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None

    # data-check-string
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(
        b"WebAppData",
        TELEGRAM_BOT_TOKEN.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    calculated = hmac.new(
        secret_key,
        data_check.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        logger.warning("Telegram initData: hash mismatch")
        return None

    # Свежесть
    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        return None
    if auth_date <= 0 or abs(int(time.time()) - auth_date) > TG_INIT_DATA_MAX_AGE:
        logger.warning("Telegram initData: auth_date expired")
        return None

    user_raw = pairs.get("user")
    if not user_raw:
        return None
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(user, dict) or "id" not in user:
        return None
    return user


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    admin = _find_admin(req.username)
    if admin is None or not _verify_password(req.password, admin["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    token = _create_token(admin["username"])
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"success": True, "username": admin["username"]})
    _set_auth_cookie(resp, token, request)
    return resp


@router.post("/telegram")
async def login_telegram_webapp(req: TelegramWebAppLoginRequest, request: Request):
    """Авто-вход из Telegram Mini App / WebApp по ID админа бота.

    Без логина/пароля: проверяем initData бота + ID ∈ TELEGRAM_ADMIN_IDS.
    """
    user = _validate_telegram_webapp_init_data(req.init_data)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные данные Telegram",
        )

    try:
        tg_id = int(user["id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Нет ID пользователя")

    if not TELEGRAM_ADMIN_IDS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TELEGRAM_ADMIN_IDS не настроен на панели",
        )
    if tg_id not in TELEGRAM_ADMIN_IDS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа: ваш Telegram ID не в списке админов",
        )

    # Сессия панели: tg:7240246267
    username = f"tg:{tg_id}"
    token = _create_token(username)
    display = user.get("username") or user.get("first_name") or str(tg_id)
    from fastapi.responses import JSONResponse
    resp = JSONResponse({
        "success": True,
        "username": username,
        "display": display,
        "telegram_id": tg_id,
    })
    _set_auth_cookie(resp, token, request)
    logger.info("Telegram WebApp login ok: tg_id=%s", tg_id)
    return resp


@router.post("/logout")
async def logout():
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"success": True})
    resp.delete_cookie(key=COOKIE_NAME, path="/")
    return resp


@router.get("/me")
async def me(username: str = Depends(get_current_user)):
    return {"username": username}
@router.get("/admins")
async def list_admins(username: str = Depends(get_current_user)):
    admins = _load_admins()
    return {"admins": [{"username": a["username"]} for a in admins]}
@router.post("/admins")
async def add_admin(req: AddAdminRequest, current: str = Depends(get_current_user)):
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Пароль слишком короткий (минимум 8 символов)")
    admins = _load_admins()
    if any(a["username"] == req.username for a in admins):
        raise HTTPException(status_code=400, detail="Админ с таким именем уже существует")
    admins.append({"username": req.username, "password_hash": _hash_password(req.password)})
    _save_admins(admins)
    return {"success": True, "username": req.username}
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
@router.post("/password")
async def change_password(req: ChangePasswordRequest, current: str = Depends(get_current_user)):
    admin = _find_admin(current)
    if admin is None or not _verify_password(req.old_password, admin["password_hash"]):
        raise HTTPException(status_code=400, detail="Старый пароль неверен")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Пароль слишком короткий (минимум 8 символов)")
    admins = _load_admins()
    for a in admins:
        if a["username"] == current:
            a["password_hash"] = _hash_password(req.new_password)
            break
    _save_admins(admins)
    return {"success": True}
class RemoveAdminRequest(BaseModel):
    username: str
@router.post("/admins/remove")
async def remove_admin(req: RemoveAdminRequest, current: str = Depends(get_current_user)):
    if req.username == current:
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
    admins = _load_admins()
    new_admins = [a for a in admins if a["username"] != req.username]
    if len(new_admins) == len(admins):
        raise HTTPException(status_code=404, detail="Админ не найден")
    if not new_admins:
        raise HTTPException(status_code=400, detail="Нельзя удалить последнего админа")
    _save_admins(new_admins)
    return {"success": True}
