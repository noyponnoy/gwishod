import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request

from src.db.v1.user_pojo import UserPojo

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/vpn/api/v1/user/subscription")
async def update_subscription(request: Request):
    body = await request.body()
    request_body = body.decode("utf-8")

    params_map: dict[str, str] = {}
    for pair in request_body.split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            params_map[parts[0]] = parts[1]

    user_id = ""
    if "userId" in params_map:
        user_id = params_map["userId"].replace("\r", "").replace("\n", "").strip()
    if "deviceId" in params_map and not user_id:
        user_id = params_map["deviceId"].replace("\r", "").replace("\n", "").strip()

    if not user_id:
        return {
            "success": 0,
            "message": "userId is required",
            "data": {},
        }

    user = UserPojo()
    user.id = user_id
    user.device_id = user_id

    if not await user.is_exist():
        return {
            "success": 0,
            "message": "user not found",
            "data": {},
        }

    user = await user.find()

    premium_duration = params_map.get("premiumDuration", "")
    if premium_duration:
        try:
            days = int(premium_duration)
            user.is_premium = True
            user.premium_end = datetime.now(timezone.utc) + timedelta(days=days)
        except ValueError:
            pass

    is_premium = params_map.get("isPremium", "")
    if is_premium.lower() in ("true", "1"):
        user.is_premium = True
    elif is_premium.lower() in ("false", "0"):
        user.is_premium = False

    premium_end = params_map.get("premiumEnd", "")
    if premium_end:
        try:
            user.premium_end = datetime.fromisoformat(premium_end)
        except ValueError:
            pass

    await user.update()

    logger.info("Subscription updated for user: %s, isPremium: %s", user_id, user.is_premium)

    return {
        "success": 1,
        "message": "success",
        "data": {},
    }
