import logging

from fastapi import Query as QueryParam
from starlette.responses import JSONResponse

from src.db.v3.servers.server_pojo import ServerPojo
from src.db.v3.user.user_pojo import UserPojo
from src.endpoints.response_object import ResponseJson, ResponseJsonMessage

logger = logging.getLogger(__name__)


async def get_servers(user_id: str = QueryParam(...)):
    user = UserPojo()
    user.user_id = user_id

    if await user.is_exist():
        user = await user.find_by_user_id()
    else:
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=404, info="user not found"),
                data={},
            ).to_dict(),
        )

    if user.is_premium:
        servers = await ServerPojo.find_all_with_premium()
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(
                    status_code=200, info="servers with premium"
                ),
                data=[s.to_doc() for s in servers],
            ).to_dict(),
        )
    else:
        servers = await ServerPojo.all_without_premium()
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(
                    status_code=200, info="servers without premium"
                ),
                data=[s.to_doc() for s in servers],
            ).to_dict(),
        )
