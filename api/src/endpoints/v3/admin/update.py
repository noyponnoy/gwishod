import json
import logging

from fastapi import Request
from starlette.responses import JSONResponse

from src.db.v3.admin.admin_pojo import AdminPojo
from src.db.v3.user.user_pojo import UserPojo
from src.endpoints.response_object import ResponseJson, ResponseJsonMessage

logger = logging.getLogger(__name__)


async def update_user(request: Request):
    admin_user = AdminPojo()
    admin_user.token = request.headers.get("Authorization", "")
    admin_user = await admin_user.find_by_token()
    if not admin_user or not await admin_user.is_exist():
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(
                    status_code=404, info="Admin not found"
                ),
                data={},
            ).to_dict(),
        )

    if await admin_user.check_token():
        body = (await request.body()).decode("utf-8")
        try:
            user = UserPojo.from_doc(json.loads(body))
        except Exception:
            return JSONResponse(
                status_code=400,
                content=ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=400, info="User Object error"
                    ),
                    data={},
                ).to_dict(),
            )
        if await user.is_exist():
            await user.update()
            return JSONResponse(
                status_code=200,
                content=ResponseJson(
                    success=True,
                    message=ResponseJsonMessage(
                        status_code=200, info="User updated"
                    ),
                    data={},
                ).to_dict(),
            )
        else:
            return JSONResponse(
                status_code=401,
                content=ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=401, info="Token expired"
                    ),
                    data={},
                ).to_dict(),
            )
    else:
        return JSONResponse(
            status_code=401,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(
                    status_code=401, info="Token not found"
                ),
                data={},
            ).to_dict(),
        )
