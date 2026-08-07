import json
import logging

from fastapi import Query as QueryParam, Request
from starlette.responses import JSONResponse

from src.client_hiddify_api.methods.api_admin import create_a_user
from src.client_hiddify_api.schemas.user import User
from src.db.v1.user_pojo import UserPojo as UserPojoV1
from src.db.v3.hiddify.configs_pojo import ConfigPojo, ConfigsPojo
from src.db.v3.hiddify.servers_pojo import ServerPojo
from src.db.v3.hiddify.user_pojo import UserPojo
from src.db.v3.user.user_pojo import UserPojo as UserPojoV3
from src.endpoints.response_object import ResponseJson, ResponseJsonMessage

logger = logging.getLogger(__name__)


async def login_or_create_user(request: Request):
    body = (await request.body()).decode("utf-8")
    user_bot = UserPojo.from_doc(json.loads(body))
    user_bot = await user_bot.find_by_tg_id()
    if user_bot and await user_bot.is_exist():
        old_user = UserPojoV1()
        old_user.device_id = user_bot.device_id
        oldjson = {
            "id": "",
            "is_anonymous": False,
            "total_download": 0,
            "total_upload": 0,
            "device_id": "",
            "source_ip": "",
            "country_code": "",
            "email": "",
            "created_at": 0,
            "last_login": 0,
            "is_premium": False,
            "premium_end": 0,
        }

        if await old_user.is_exist():
            old_user = await old_user.find()
            oldjson = {
                "id": old_user.id if hasattr(old_user, 'id') else "",
                "is_anonymous": old_user.is_anonymous,
                "total_download": old_user.total_download,
                "total_upload": old_user.total_upload,
                "device_id": old_user.device_id,
                "source_ip": old_user.source_ip,
                "country_code": old_user.country_code,
                "email": old_user.email,
                "created_at": str(old_user.created_at),
                "last_login": str(old_user.last_login),
                "is_premium": old_user.is_premium,
                "premium_end": str(old_user.premium_end),
            }

        new_user = UserPojoV3()
        new_user.user_id = user_bot.user_id
        if await new_user.is_exist():
            pass  # new_user = new_user.find_by_user_id()

        response_data = {
            "old_user_data": oldjson,
            "user_data": new_user.to_doc(),
            "hiddify_user_data": user_bot.to_doc(),
        }
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="User found"),
                data=response_data,
            ).to_dict(),
        )
    else:
        if await user_bot.insert():
            return JSONResponse(
                status_code=200,
                content=ResponseJson(
                    success=True,
                    message=ResponseJsonMessage(
                        status_code=200, info="User created"
                    ),
                    data=user_bot.to_doc(),
                ).to_dict(),
            )
        else:
            return JSONResponse(
                status_code=500,
                content=ResponseJson(
                    success=False,
                    message=ResponseJsonMessage(
                        status_code=500, info="User not created"
                    ),
                    data=user_bot.to_doc(),
                ).to_dict(),
            )


async def get_user_configs(tg_id: str = QueryParam(...)):
    configs = ConfigsPojo()
    configs.tg_id = tg_id
    configs_list = await configs.find_all_by_tg_id()
    return JSONResponse(
        status_code=200,
        content=ResponseJson(
            success=True,
            message=ResponseJsonMessage(status_code=200, info="Configs found"),
            data=[c.to_doc() for c in configs_list] if configs_list else [],
        ).to_dict(),
    )


async def create_user_configs(tg_id: str = QueryParam(...)):
    user_bot = UserPojo()
    user_bot.tg_id = tg_id
    is_premium = False
    if await user_bot.is_exist():
        user_old = UserPojoV1()
        user_new = UserPojoV3()
        user_old.device_id = user_bot.device_id
        user_new.user_id = user_bot.user_id
        if await user_old.is_exist():
            user_old = await user_old.find()
            is_premium = user_old.is_premium
        if await user_new.is_exist():
            is_premium = user_new.is_premium

    config_vec = []
    if is_premium:
        servers = await ServerPojo.find_all()
    else:
        servers = await ServerPojo.all_without_premium()

    for server in servers:
        config = ConfigPojo()
        config.server_ip_address = server.ip_address
        if not server.premium:
            user_schema = User()
            user_schema.telegram_id = int(user_bot.tg_id)
            user_schema.enable = True
            user_schema.is_active = True
            user_schema.lang = "ru"
            user_schema.mode = "daily"
            user_schema.name = user_bot.tg_id
            user_schema.usage_limit_GB = 9999
            cf = await create_a_user(
                server.ip_address,
                server.path,
                server.admin_uuid,
                user_schema,
            )
            config.config = (
                f"https://{server.server_address}/{server.path_user}/"
                f"{cf.uuid}/auto/"
            )
            config_vec.append(config)

    configs = ConfigsPojo()
    configs.tg_id = tg_id
    if await configs.insert():
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(
                    status_code=200, info="Configs created"
                ),
                data=configs.to_doc(),
            ).to_dict(),
        )
    else:
        return JSONResponse(
            status_code=500,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(
                    status_code=500, info="Configs not created"
                ),
                data=configs.to_doc(),
            ).to_dict(),
        )
