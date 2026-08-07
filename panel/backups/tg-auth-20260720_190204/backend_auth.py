from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from pydantic import BaseModel
from .config import JWT_ALGORITHM, JWT_EXPIRE_DAYS, JWT_SECRET, _hash_password, _load_admins, _save_admins
router = APIRouter(prefix="/api/auth", tags=["auth"])
COOKIE_NAME = "gw_panel_token"
class LoginRequest(BaseModel):
    username: str
    password: str
class AdminInfo(BaseModel):
    username: str
class AddAdminRequest(BaseModel):
    username: str
    password: str
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
def get_current_user(token: Optional[str] = Cookie(default=None, alias=COOKIE_NAME)) -> str:
    username = _decode_token(token)
    if username is None or _find_admin(username) is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован",
        )
    return username
@router.post("/login")
async def login(req: LoginRequest, request: Request):
    admin = _find_admin(req.username)
    if admin is None or not _verify_password(req.password, admin["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    token = _create_token(admin["username"])
    is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
    from fastapi.responses import JSONResponse
    resp = JSONResponse({"success": True, "username": admin["username"]})
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=JWT_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=is_https,
        samesite="lax",
        path="/",
    )
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
