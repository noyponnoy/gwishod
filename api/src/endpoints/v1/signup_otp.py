import logging

from fastapi import APIRouter, Request

from src.db.v1.otp_pojo import OtpPojo
from src.db.v1.user_pojo import UserPojo, UserJson

logger = logging.getLogger(__name__)

router = APIRouter()


async def _go(request_body: str, user_ip: str) -> dict:
    params_map: dict[str, str] = {}
    for pair in request_body.split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            params_map[parts[0]] = parts[1]

    device_id = ""
    if "deviceId" in params_map:
        device_id = params_map["deviceId"].replace("\r", "").replace("\n", "").strip()
    if "userId" in params_map:
        device_id = params_map["userId"].replace("\r", "").replace("\n", "").strip()

    user = UserPojo()
    user.id = device_id
    user.device_id = device_id
    user.source_ip = user_ip
    user.email = device_id

    if await user.is_exist():
        user = await user.find()
        user.last_login = UserPojo.now()
        await user.update()
    else:
        await user.insert()
        logger.info("User: %s logged created", user.id)

    user_json = UserJson.from_pojo(user)

    return {
        "success": 1,
        "message": "success",
        "data": user_json.to_dict(),
    }


@router.post("/vpn/api/v1/user/signup")
async def signup(request: Request):
    body = await request.body()
    request_body = body.decode("utf-8")

    params_map: dict[str, str] = {}
    for pair in request_body.split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            params_map[parts[0]] = parts[1]

    email = params_map.get("email", "").replace("\r", "").replace("\n", "").strip()
    if not email:
        return {
            "success": 0,
            "message": "email is required",
            "data": {},
        }

    otp = OtpPojo()
    otp.email = email
    otp.code = OtpPojo.generate_code()
    await otp.insert()

    logger.info("OTP generated for email: %s, code: %s", email, otp.code)

    return {
        "success": 1,
        "message": "success",
        "data": {},
    }


@router.post("/vpn/api/v1/user/otp")
async def otp_verify(request: Request):
    body = await request.body()
    request_body = body.decode("utf-8")
    user_ip = request.client.host if request.client else ""

    params_map: dict[str, str] = {}
    for pair in request_body.split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            params_map[parts[0]] = parts[1]

    email = params_map.get("email", "").replace("\r", "").replace("\n", "").strip()
    code = params_map.get("code", "").replace("\r", "").replace("\n", "").strip()

    if not email or not code:
        return {
            "success": 0,
            "message": "email and code are required",
            "data": {},
        }

    otp = await OtpPojo.find_valid(email, code)
    if otp is None:
        return {
            "success": 0,
            "message": "invalid or expired code",
            "data": {},
        }

    await otp.mark_used()

    user = UserPojo()
    user.email = email
    user.device_id = email
    user.id = email
    user.source_ip = user_ip
    user.is_anonymous = False

    if await user.is_exist():
        user = await user.find()
        user.last_login = UserPojo.now()
        await user.update()
    else:
        await user.insert()
        logger.info("User created via OTP: %s", email)

    user_json = UserJson.from_pojo(user)

    return {
        "success": 1,
        "message": "success",
        "data": user_json.to_dict(),
    }
