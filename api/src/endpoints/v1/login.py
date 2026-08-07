import logging
from urllib.parse import parse_qsl, unquote_plus

from fastapi import APIRouter, Request

from src.db.v1.user_pojo import UserPojo, UserJson

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/vpn/api/v1/user/loginAnonymousUser")
async def login_anonymous_user(request: Request):
    body = await request.body()
    request_body = body.decode("utf-8")
    user_ip = request.client.host if request.client else ""
    result = await _go(request_body, user_ip)
    return result


@router.post("/vpn/api/v1/user/profile")
async def profile(request: Request):
    body = await request.body()
    request_body = body.decode("utf-8")
    user_ip = request.client.host if request.client else ""
    result = await _go(request_body, user_ip)
    return result


async def _go(request_body: str, user_ip: str) -> dict:
    """Вход / профиль. Здесь безопасно пишем platform (редко, не heartbeat)."""
    try:
        params_map = dict(parse_qsl(request_body, keep_blank_values=True))
    except Exception:
        params_map = {}
        for pair in request_body.split("&"):
            parts = pair.split("=", 1)
            if len(parts) == 2:
                params_map[parts[0]] = unquote_plus(parts[1])

    device_id = ""
    if "deviceId" in params_map:
        device_id = params_map["deviceId"].replace("\r", "").replace("\n", "").strip()
    if "userId" in params_map:
        device_id = params_map["userId"].replace("\r", "").replace("\n", "").strip()

    # bundleId: app.greywebs.vpn (Android) / com.greywebs.greywebsvpn (iOS)
    # НЕ обрабатываем heartbeat здесь — только login/profile.
    bundle_id = (params_map.get("bundleId") or "").strip()

    user = UserPojo()
    user.id = device_id
    user.device_id = device_id
    user.source_ip = user_ip
    user.email = device_id
    user.apply_bundle_id(bundle_id)

    if await user.is_exist():
        existing = await user.find()
        if existing is None:
            await user.insert()
            logger.info("User: %s logged created", user.id)
        else:
            existing.last_login = UserPojo.now()
            if user_ip:
                existing.source_ip = user_ip
            # Обновляем platform только если bundleId валидный
            existing.apply_bundle_id(bundle_id)
            await existing.update()
            user = existing
    else:
        await user.insert()
        logger.info("User: %s logged created", user.id)

    user_json = UserJson.from_pojo(user)

    return {
        "success": 1,
        "message": "success",
        "data": user_json.to_dict(),
    }
