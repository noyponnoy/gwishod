import json
import logging

from fastapi import Request
from starlette.responses import JSONResponse

from src.db.v3.user.user_pojo import UserPojo
from src.endpoints.response_object import ResponseJson, ResponseJsonMessage

logger = logging.getLogger(__name__)


async def insert(request: Request):
    body = (await request.body()).decode("utf-8")
    try:
        user = UserPojo.from_doc(json.loads(body))
    except Exception:
        return JSONResponse(
            status_code=400,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=400, info="User Object error"),
                data={},
            ).to_dict(),
        )

    if await user.is_exist():
        return JSONResponse(
            status_code=409,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=409, info="User already exist"),
                data={},
            ).to_dict(),
        )
    else:
        await user.insert()
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="User inserted"),
                data={},
            ).to_dict(),
        )


async def update(request: Request):
    body = (await request.body()).decode("utf-8")
    try:
        user = UserPojo.from_doc(json.loads(body))
    except Exception:
        return JSONResponse(
            status_code=400,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=400, info="User Object error"),
                data={},
            ).to_dict(),
        )

    if await user.is_exist():
        await user.update()
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="User updated"),
                data={},
            ).to_dict(),
        )
    else:
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=404, info="User not found"),
                data={},
            ).to_dict(),
        )


async def delete(request: Request):
    body = (await request.body()).decode("utf-8")
    try:
        user = UserPojo.from_doc(json.loads(body))
    except Exception:
        return JSONResponse(
            status_code=400,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=400, info="User Object error"),
                data={},
            ).to_dict(),
        )

    if await user.is_exist():
        await user.delete()
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="User deleted"),
                data={},
            ).to_dict(),
        )
    else:
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=404, info="User not found"),
                data={},
            ).to_dict(),
        )


async def find(request: Request):
    body = (await request.body()).decode("utf-8")
    try:
        user = UserPojo.from_doc(json.loads(body))
    except Exception:
        return JSONResponse(
            status_code=400,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=400, info="User Object error"),
                data={},
            ).to_dict(),
        )

    if await user.is_exist():
        user = await user.find_by_user_id()
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="User found"),
                data=user.to_doc(),
            ).to_dict(),
        )
    else:
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=404, info="User not found"),
                data={},
            ).to_dict(),
        )


async def find_all():
    users = await UserPojo.find_all()
    return JSONResponse(
        status_code=200,
        content=ResponseJson(
            success=True,
            message=ResponseJsonMessage(status_code=200, info="Users found"),
            data=[u.to_doc() for u in users],
        ).to_dict(),
    )
