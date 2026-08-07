import json
import logging
import time

from fastapi import Query as QueryParam, Request
from starlette.responses import JSONResponse, Response

from src.db.v3.code.code_pojo import CodePojo
from src.db.v3.user.traffic_history_pojo import TrafficHistory
from src.db.v3.user.user_pojo import UserPojo
from src.endpoints.response_object import ResponseJson, ResponseJsonMessage
from src.utils import crypto_user

logger = logging.getLogger(__name__)


async def create(request: Request):
    user = UserPojo()
    mnemonic = await crypto_user.generate_mnemonic()
    xprv = await crypto_user.mnemonic_to_xprv(mnemonic)
    user_id = xprv.public_key().to_bytes().hex()
    user.user_id = user_id
    while await user.is_exist():
        mnemonic = await crypto_user.generate_mnemonic()
        xprv = await crypto_user.mnemonic_to_xprv(mnemonic)
        user_id = xprv.public_key().to_bytes().hex()
        user.user_id = user_id

    user.created_at = int(time.time() * 1000)
    user.last_login = int(time.time() * 1000)
    user.source_ip = request.client.host if request.client else ""

    if await user.insert():
        logger.info(f"User: {user.user_id} created")
        resp = Response(
            content=json.dumps(
                ResponseJson(
                    success=True,
                    message=ResponseJsonMessage(status_code=200, info="User created"),
                    data=user.to_doc(),
                ).to_dict(),
                default=str,
            ),
            status_code=200,
            media_type="application/json",
        )
        resp.headers["Mnemonic"] = mnemonic
        return resp
    else:
        logger.error(f"User: {user.user_id} creation failed")
        resp = Response(
            content=json.dumps(
                ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=500, info="User creation failed"
                    ),
                    data={},
                ).to_dict(),
                default=str,
            ),
            status_code=500,
            media_type="application/json",
        )
        resp.headers["Mnemonic"] = ""
        return resp


async def get(user_id: str = QueryParam(...)):
    user = UserPojo()
    user.user_id = user_id
    if await user.is_exist():
        user = await user.find_by_user_id()
        user.last_login = int(time.time() * 1000)
        if not await user.update():
            logger.error(f"User: {user.user_id} last login not updated")
            return JSONResponse(
                status_code=500,
                content=ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=500, info="User last login not updated"
                    ),
                    data={},
                ).to_dict(),
            )
        logger.info(f"User: {user.user_id} found")
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="User found"),
                data=user.to_doc(),
            ).to_dict(),
        )
    else:
        logger.error(f"User: {user.user_id} not found")
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=404, info="User not found"),
                data={},
            ).to_dict(),
        )


async def update_traffic(request: Request):
    body = (await request.body()).decode("utf-8")
    try:
        traffic = TrafficHistory.from_doc(json.loads(body))
    except Exception:
        return JSONResponse(
            status_code=400,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(
                    status_code=400, info="Traffic Object error"
                ),
                data={},
            ).to_dict(),
        )

    if await traffic.insert():
        userp = UserPojo()
        userp.user_id = traffic.user_id
        if await userp.is_exist():
            userp = await userp.find_by_user_id()
            userp.last_login = int(time.time() * 1000)
            userp.source_ip = request.client.host if request.client else ""
            userp.total_upload += traffic.upload
            userp.total_download += traffic.download
            if not await userp.update():
                logger.error(f"User: {userp.user_id} traffic not updated")
                return JSONResponse(
                    status_code=500,
                    content=ResponseJson(
                        success=False,
                        message=ResponseJsonMessage(
                            status_code=500, info="User traffic not updated"
                        ),
                        data={},
                    ).to_dict(),
                )
        else:
            logger.error(f"User: {userp.user_id} not found")
            return JSONResponse(
                status_code=404,
                content=ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=404, info="User not found"
                    ),
                    data={},
                ).to_dict(),
            )
        logger.info(f"User: {userp.user_id} traffic inserted")
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(
                    status_code=200, info="Traffic inserted"
                ),
                data={},
            ).to_dict(),
        )
    else:
        logger.error(f"User: {traffic.user_id} traffic not inserted")
        return JSONResponse(
            status_code=500,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(
                    status_code=500, info="Traffic not inserted"
                ),
                data={},
            ).to_dict(),
        )


async def login(mnemonic: str = QueryParam(...)):
    user = UserPojo()
    xprv = await crypto_user.mnemonic_to_xprv(mnemonic)
    user_id = xprv.public_key().to_bytes().hex()
    user.user_id = user_id
    if await user.is_exist():
        user = await user.find_by_user_id()
        user.last_login = int(time.time() * 1000)
        if await user.update():
            logger.info(f"User: {user.user_id} logged in")
            return JSONResponse(
                status_code=200,
                content=ResponseJson(
                    success=True,
                    message=ResponseJsonMessage(
                        status_code=200, info="User logged in"
                    ),
                    data=user.to_doc(),
                ).to_dict(),
            )
        else:
            logger.error(f"User: {user.user_id} login failed")
            return JSONResponse(
                status_code=500,
                content=ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=500, info="User login failed"
                    ),
                    data={},
                ).to_dict(),
            )
    else:
        logger.error(f"User: {user.user_id} not found")
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(
                    status_code=404, info="User not found. Login failed"
                ),
                data={},
            ).to_dict(),
        )


async def activate_code(
    user_id: str = QueryParam(...), code: str = QueryParam(...)
):
    code_pojo = CodePojo()
    code_pojo.code = code
    if await code_pojo.is_exist():
        code_pojo = await code_pojo.find_by_code()
        if code_pojo.used:
            logger.error(f"Code: {code_pojo.code} already used")
            return JSONResponse(
                status_code=400,
                content=ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=400, info="Code already used"
                    ),
                    data={},
                ).to_dict(),
            )
        user = UserPojo()
        user.user_id = user_id
        if await user.is_exist():
            user = await user.find_by_user_id()
            now_ms = int(time.time() * 1000)
            if user.premium_end < now_ms:
                user.premium_end = now_ms + code_pojo.duration
            else:
                user.premium_end = user.premium_end + code_pojo.duration
            user.is_premium = True
            if await user.update():
                code_pojo.used = True
                code_pojo.user_used_id = user.user_id
                code_pojo.used_date = now_ms
                if await code_pojo.update():
                    logger.info(f"Code: {code_pojo.code} activated")
                    return JSONResponse(
                        status_code=200,
                        content=ResponseJson(
                            success=True,
                            message=ResponseJsonMessage(
                                status_code=200, info="Code activated"
                            ),
                            data={},
                        ).to_dict(),
                    )
                else:
                    logger.error(f"Code: {code_pojo.code} not activated")
                    return JSONResponse(
                        status_code=500,
                        content=ResponseJson(
                            success=False,
                            message=ResponseJsonMessage(
                                status_code=500, info="Code not activated"
                            ),
                            data={},
                        ).to_dict(),
                    )
            else:
                logger.error(f"User: {user.user_id} not updated")
                return JSONResponse(
                    status_code=500,
                    content=ResponseJson(
                        success=False,
                        message=ResponseJsonMessage(
                            status_code=500, info="User not updated"
                        ),
                        data={},
                    ).to_dict(),
                )
        else:
            logger.error(f"User: {user.user_id} not found")
            return JSONResponse(
                status_code=404,
                content=ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=404, info="User not found"
                    ),
                    data={},
                ).to_dict(),
            )
    else:
        logger.error(f"Code: {code_pojo.code} not found")
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(
                    status_code=404, info="Code not found"
                ),
                data={},
            ).to_dict(),
        )
