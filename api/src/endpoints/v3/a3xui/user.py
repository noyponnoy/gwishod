import asyncio
import json
import logging

from urllib.parse import quote

from fastapi import Query as QueryParam, Path
from starlette.responses import PlainTextResponse

from src.client_3xui_api import client
from src.db.v3.a3xui.tariff_pojo import TariffPojo
from src.db.v3.a3xui.user_pojo import UserPojo

logger = logging.getLogger(__name__)

import httpx


async def create_or_login(tg_id: str = QueryParam(...)):
    if await client.create_user(tg_id):
        return PlainTextResponse("User created", status_code=200)
    else:
        return PlainTextResponse("User logged in", status_code=200)


async def set_free(tg_id: str = QueryParam(...)):
    if await client.create_free_access(tg_id):
        async with httpx.AsyncClient() as http_client:
            url = (
                f"http://localhost:8080/notification?"
                f"tg_id={quote(tg_id)}"
                f"&message={quote('Вам предоставлен Lite тариф на 3 дня!')}"
                f"&image={quote('null')}"
                f"&type={quote('ALERT')}"
                f"&fileType={quote('null')}"
            )
            await http_client.get(url)
        return PlainTextResponse("OK", status_code=200)
    else:
        return PlainTextResponse("Error", status_code=200)


async def update_payment_hand(tg_id: str = QueryParam(...), t_name: int = QueryParam(...)):
    if await client.update_user_payment(tg_id, t_name, None):
        url = ""
        if t_name == 1:
            url = (
                f"http://localhost:8080/notification?"
                f"tg_id={quote(tg_id)}"
                f"&message={quote('Тариф Lite активирован на 30 дней!')}"
                f"&image={quote('null')}"
                f"&type={quote('ALERT')}"
                f"&fileType={quote('null')}"
            )
        if t_name == 2:
            url = (
                f"http://localhost:8080/notification?"
                f"tg_id={quote(tg_id)}"
                f"&message={quote('Тариф Pro активирован на 30 дней!')}"
                f"&image={quote('null')}"
                f"&type={quote('ALERT')}"
                f"&fileType={quote('null')}"
            )
        try:
            async with httpx.AsyncClient() as http_client:
                await http_client.get(url)
            return PlainTextResponse("OK", status_code=200)
        except Exception as e:
            logger.error(str(e))
            return PlainTextResponse("Error", status_code=200)
    else:
        return PlainTextResponse("Error", status_code=200)


async def get_user_exps(tg_id: str = QueryParam(...)):
    exps = await client.get_user_exps(tg_id)
    return PlainTextResponse(exps, status_code=200)


async def get_user_subscription(tg_id: str = Path(...)):
    subs = await client.get_user_subscription(tg_id)
    return PlainTextResponse(subs, status_code=200)


async def get_user_subscription_sname(tg_id: str = Path(...), subsname: str = Path(...)):
    subs = await client.get_user_subscription(tg_id)
    return PlainTextResponse(subs, status_code=200)


async def get_tarrifs():
    tariffs = await TariffPojo.find_all()
    return PlainTextResponse(
        json.dumps([t.to_doc() for t in tariffs], default=str),
        status_code=200,
    )


async def get_dates(tg_id: str = QueryParam(...)):
    user = UserPojo()
    user.tg_id = tg_id
    user = await user.find()
    return PlainTextResponse(json.dumps(user.to_doc(), default=str), status_code=200)
