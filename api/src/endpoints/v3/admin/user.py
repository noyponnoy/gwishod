import base64
import hashlib
import logging
import time
import uuid

from fastapi import Query as QueryParam, Request
from starlette.responses import JSONResponse

from src.db.v3.admin.admin_pojo import AdminPojo
from src.endpoints.response_object import ResponseJson, ResponseJsonMessage

logger = logging.getLogger(__name__)


async def create(request: Request, login: str = QueryParam(...), password: str = QueryParam(...)):
    admin_user = AdminPojo()
    admin_user.token = request.headers.get("Authorization", "")
    admin_user = await admin_user.find_by_token()
    if not admin_user or not admin_user.login:
        return JSONResponse(
            status_code=401,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=401, info="Unauthorized"),
                data={},
            ).to_dict(),
        )

    if await admin_user.check_token():
        new_admin_user = AdminPojo()
        new_admin_user.login = login
        hash_bytes = hashlib.sha256(
            password.encode("utf-8") + login.encode("utf-8")
        ).digest()
        new_admin_user.hash = base64.b64encode(hash_bytes).decode("utf-8")
        if await new_admin_user.is_exist():
            return JSONResponse(
                status_code=409,
                content=ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(status_code=409, info="Conflict"),
                    data={},
                ).to_dict(),
            )
        else:
            if await new_admin_user.insert():
                return JSONResponse(
                    status_code=201,
                    content=ResponseJson(
                        success=True,
                        message=ResponseJsonMessage(
                            status_code=201, info="Created"
                        ),
                        data={},
                    ).to_dict(),
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content=ResponseJson(
                        success=False,
                        message=ResponseJsonMessage(
                            status_code=500, info="Internal Server Error"
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


async def login(login_param: str = QueryParam(..., alias="login"), password: str = QueryParam(...)):
    admin_user = AdminPojo()
    admin_user.login = login_param
    admin_user = await admin_user.find_by_login()
    if not admin_user:
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(
                    status_code=404, info="Not found user"
                ),
                data={},
            ).to_dict(),
        )

    if await admin_user.is_exist():
        if await admin_user.check_password(password):
            token = base64.b64encode(uuid.uuid4().bytes).decode("utf-8")
            admin_user.token = token
            admin_user.expire = int(time.time() * 1000) + 900000  # 15 minutes
            if await admin_user.update():
                return JSONResponse(
                    status_code=200,
                    content=ResponseJson(
                        success=True,
                        message=ResponseJsonMessage(
                            status_code=200, info="OK"
                        ),
                        data=token,
                    ).to_dict(),
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content=ResponseJson(
                        success=False,
                        message=ResponseJsonMessage(
                            status_code=500, info="Internal Server Error"
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
                        status_code=401, info="Unauthorized"
                    ),
                    data={},
                ).to_dict(),
            )
    else:
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(
                    status_code=404, info="Not found user"
                ),
                data={},
            ).to_dict(),
        )


async def update(
    request: Request,
    login_param: str = QueryParam(..., alias="login"),
    password: str = QueryParam(...),
):
    admin_user = AdminPojo()
    admin_user.token = request.headers.get("Authorization", "")
    admin_user = await admin_user.find_by_token()
    if not admin_user or not admin_user.login:
        return JSONResponse(
            status_code=401,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=401, info="Unauthorized"),
                data={},
            ).to_dict(),
        )

    if await admin_user.check_token():
        hash_bytes = hashlib.sha256(
            password.encode("utf-8") + login_param.encode("utf-8")
        ).digest()
        admin_user.hash = base64.b64encode(hash_bytes).decode("utf-8")
        if await admin_user.update():
            return JSONResponse(
                status_code=200,
                content=ResponseJson(
                    success=True,
                    message=ResponseJsonMessage(
                        status_code=200, info="Password updated"
                    ),
                    data={},
                ).to_dict(),
            )
        else:
            return JSONResponse(
                status_code=500,
                content=ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=500, info="Internal Server Error"
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


async def delete(
    request: Request,
    login_param: str = QueryParam(..., alias="login"),
    password: str = QueryParam(...),
):
    admin_user = AdminPojo()
    admin_user.token = request.headers.get("Authorization", "")
    admin_user = await admin_user.find_by_token()
    if not admin_user or not admin_user.login:
        return JSONResponse(
            status_code=401,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=401, info="Unauthorized"),
                data={},
            ).to_dict(),
        )

    if await admin_user.check_token():
        new_admin_user = AdminPojo()
        new_admin_user.login = login_param
        if await new_admin_user.delete():
            return JSONResponse(
                status_code=200,
                content=ResponseJson(
                    success=True,
                    message=ResponseJsonMessage(
                        status_code=200, info="Deleted"
                    ),
                    data={},
                ).to_dict(),
            )
        else:
            return JSONResponse(
                status_code=500,
                content=ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=500, info="Internal Server Error"
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


async def update_token(request: Request):
    admin_user = AdminPojo()
    admin_user.token = request.headers.get("Authorization", "")
    admin_user = await admin_user.find_by_token()
    if not admin_user or not admin_user.login:
        return JSONResponse(
            status_code=401,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=401, info="Unauthorized"),
                data={},
            ).to_dict(),
        )

    if await admin_user.check_token():
        admin_user.expire = int(time.time() * 1000) + 900000  # 15 minutes
        if await admin_user.update():
            return JSONResponse(
                status_code=200,
                content=ResponseJson(
                    success=True,
                    message=ResponseJsonMessage(
                        status_code=200, info="Token expired time updated"
                    ),
                    data={},
                ).to_dict(),
            )
        else:
            return JSONResponse(
                status_code=500,
                content=ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=500, info="Internal Server Error"
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
