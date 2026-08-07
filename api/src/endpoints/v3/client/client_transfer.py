import json
import logging
import time

from fastapi import Query as QueryParam
from starlette.responses import Response, JSONResponse

from src.db.v1.user_pojo import UserPojo as UserPojoV1
from src.db.v3.user.user_pojo import UserPojo as UserPojoV3
from src.endpoints.response_object import ResponseJson, ResponseJsonMessage
from src.utils import crypto_user

logger = logging.getLogger(__name__)


async def transfer(device_id: str = QueryParam(...)):
    olduser = UserPojoV1()
    olduser.device_id = device_id
    olduser = await olduser.find()

    newuser = UserPojoV3()
    mnemonic = await crypto_user.generate_mnemonic()
    xprv = await crypto_user.mnemonic_to_xprv(mnemonic)
    user_id = xprv.public_key().to_bytes().hex()
    newuser.user_id = user_id
    while await newuser.is_exist():
        mnemonic = await crypto_user.generate_mnemonic()
        xprv = await crypto_user.mnemonic_to_xprv(mnemonic)
        user_id = xprv.public_key().to_bytes().hex()
        newuser.user_id = user_id

    newuser.created_at = int(olduser.created_at.timestamp() * 1000) if hasattr(olduser.created_at, 'timestamp') else olduser.created_at
    newuser.last_login = int(olduser.last_login.timestamp() * 1000) if hasattr(olduser.last_login, 'timestamp') else olduser.last_login
    newuser.total_upload = olduser.total_upload
    newuser.total_download = olduser.total_download
    newuser.premium_end = int(olduser.premium_end.timestamp() * 1000) if hasattr(olduser.premium_end, 'timestamp') else olduser.premium_end
    newuser.is_premium = olduser.is_premium

    if await newuser.insert():
        resp = Response(
            content=json.dumps(
                ResponseJson(
                    success=True,
                    message=ResponseJsonMessage(
                        status_code=200, info="User transfered"
                    ),
                    data=newuser.to_doc(),
                ).to_dict(),
                default=str,
            ),
            status_code=200,
            media_type="application/json",
        )
        resp.headers["Mnemonic"] = mnemonic
        return resp
    else:
        resp = Response(
            content=json.dumps(
                ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=500, info="User transfer failed"
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
