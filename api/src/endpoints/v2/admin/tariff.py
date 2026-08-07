import json
import logging

from fastapi import Request
from starlette.responses import PlainTextResponse

from src.db.v1.privileges import Privileges
from src.db.v1.support_user_pojo import SupportUserPojo
from src.db.v2.tariff_pojo import TariffPojo

logger = logging.getLogger(__name__)


async def add_tariff(request: Request):
    headers = request.headers
    body = (await request.body()).decode("utf-8")
    r_user = SupportUserPojo()
    r_user.user = headers.get("supportuser", "")
    r_user = await r_user.find()
    if r_user and r_user.privileges == Privileges.ADMIN and r_user.enabled_update:
        tariff = TariffPojo.from_doc(json.loads(body))
        if await tariff.insert():
            return PlainTextResponse("Tariff added", status_code=200)
        else:
            return PlainTextResponse(
                "Internal server error. Failed to add tariff to database",
                status_code=500,
            )
    else:
        return PlainTextResponse("Forbidden", status_code=401)


async def update_tariff(request: Request):
    headers = request.headers
    body = (await request.body()).decode("utf-8")
    r_user = SupportUserPojo()
    r_user.user = headers.get("supportuser", "")
    r_user = await r_user.find()
    if r_user and r_user.privileges == Privileges.ADMIN and r_user.enabled_update:
        tariff = TariffPojo.from_doc(json.loads(body))
        if await tariff.update():
            return PlainTextResponse("Tariff updated", status_code=200)
        else:
            return PlainTextResponse(
                "Internal server error. Failed to update tariff in database",
                status_code=500,
            )
    else:
        return PlainTextResponse("Forbidden", status_code=401)


async def del_tariff(request: Request):
    headers = request.headers
    body = (await request.body()).decode("utf-8")
    r_user = SupportUserPojo()
    r_user.user = headers.get("supportuser", "")
    r_user = await r_user.find()
    if r_user and r_user.privileges == Privileges.ADMIN and r_user.enabled_update:
        tariff = TariffPojo.from_doc(json.loads(body))
        if await tariff.delete():
            return PlainTextResponse("Tariff deleted", status_code=200)
        else:
            return PlainTextResponse(
                "Internal server error. Failed to delete tariff from database",
                status_code=500,
            )
    else:
        return PlainTextResponse("Forbidden", status_code=401)
