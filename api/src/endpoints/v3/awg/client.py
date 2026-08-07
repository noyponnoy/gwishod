import logging
from fastapi import APIRouter, Request
from src.db.v3.awg.server_pojo import ServerPojo
from src.db.v1.user_pojo import UserPojo
from src.utils.awg_provisioner import get_personal_configs

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/vpn/api/v1/user/server_awg")
async def get_servers_awg(request: Request):
    try:
        body = await request.body()
        request_body = body.decode("utf-8")
        user_ip = request.client.host if request.client else ""

        params_map: dict[str, str] = {}
        for pair in request_body.split("&"):
            parts = pair.split("=", 1)
            if len(parts) == 2:
                params_map[parts[0]] = parts[1]

        user_id = params_map.get("userId", "").replace("\r", "").replace("\n", "").strip()
        if not user_id:
            return {"success": 0, "message": "userId required", "data": []}

        user = UserPojo()
        user.id = user_id
        user.device_id = user_id
        user.source_ip = user_ip
        user.email = user_id

        if await user.is_exist():
            user = await user.find()
        else:
            await user.insert()
            user = await user.find()

        servers = await ServerPojo.find_all()

        # Серверы, для которых юзеру реально отдаётся конфиг
        # (для них запрашиваем/создаём ПЕРСОНАЛЬНЫЙ peer вместо общего конфига)
        eligible_ips = [
            s.ip_address
            for s in servers
            if s.status and not (s.premium and not user.is_premium)
        ]

        # Персональные конфиги: кэш -> агент на VPS -> (None = общий конфиг).
        # Никогда не бросает и ограничен по времени — при недоступности агентов
        # юзер просто получает старый общий конфиг (как раньше).
        personal_configs: dict[str, str] = {}
        try:
            personal_configs = await get_personal_configs(user_id, eligible_ips)
        except Exception as e:
            logger.error(f"Personal AWG config provisioning failed: {e}")

        servers_json = []
        for server in servers:
            if server.status:
                if server.premium and not user.is_premium:
                    # Strip config for premium servers if user is not premium
                    doc = server.to_doc()
                    doc["config"] = ""
                    servers_json.append(doc)
                else:
                    doc = server.to_doc()
                    personal = personal_configs.get(server.ip_address)
                    if personal:
                        doc["config"] = personal
                    servers_json.append(doc)

        return {
            "success": 1,
            "error": 0,
            "message": "success",
            "data": servers_json,
        }
    except Exception as e:
        logger.error(f"Error fetching AWG servers for user: {e}")
        return {"success": 0, "message": str(e), "data": []}
