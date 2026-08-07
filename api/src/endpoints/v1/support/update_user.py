import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.db.v1.privileges import Privileges
from src.db.v1.support_user_pojo import SupportUserPojo
from src.db.v1.user_pojo import UserPojo, UserJson2

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateUserRequestJson(BaseModel):
    userData: UserJson2
    supportUser: str


@router.post("/vpn/api/v1/support/updateuser")
async def update_user(body: UpdateUserRequestJson):
    user_json = body.userData
    support_user = body.supportUser

    r_user = SupportUserPojo()
    r_user.user = support_user
    r_user = await r_user.find()

    has_permission = (
        (r_user.privileges == Privileges.ADMIN and r_user.enabled_update)
        or (r_user.privileges == Privileges.SUPPORT and r_user.enabled_update)
    )

    if has_permission:
        user = UserPojo(
            id=user_json.id,
            is_anonymous=user_json.is_anonymous,
            total_download=user_json.total_download,
            total_upload=user_json.total_upload,
            device_id=user_json.device_id,
            source_ip=user_json.source_ip,
            country_code=user_json.country_code,
            email=user_json.email,
            created_at=user_json.created_at,
            last_login=user_json.last_login,
            is_premium=user_json.is_premium,
            premium_end=user_json.premium_end,
        )
        result = await user.update()

        if result:
            return {"error": False, "message": "user updated"}
        else:
            return JSONResponse(
                status_code=500,
                content={"error": True, "message": "user not updated"},
            )
    else:
        return JSONResponse(
            status_code=401,
            content={"error": True, "message": "user not updated"},
        )
