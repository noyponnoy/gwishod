import logging

from fastapi import APIRouter, Request

from src.db.v1.user_pojo import UserPojo, UserJson

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/vpn/api/v1/user/updateTotalUploadDownload")
async def update_total_upload_download(request: Request):
    body = await request.body()
    request_body = body.decode("utf-8")

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
    user.email = device_id

    if await user.is_exist():
        user = await user.find()
        user.total_upload = user.total_upload + int(params_map["totalUpload"])
        user.total_download = user.total_download + int(params_map["totalDownload"])
        await user.update()

    user_json = UserJson.from_pojo(user)

    response = {
        "success": 1,
        "message": "success",
        "data": user_json.to_dict(),
    }

    if user.is_premium:
        logger.info(
            "Premium User: %s total upload: %s total download: %s",
            user.id, user.total_upload, user.total_download,
        )
    else:
        logger.info(
            "Free User: %s total upload: %s total download: %s",
            user.id, user.total_upload, user.total_download,
        )

    return response
