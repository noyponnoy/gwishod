"""
Эндпоинты для провижининг-агентов AWG (персональные пиры на пользователя).

- /bot/agents_awg/register   — регистрация агента (вызывается setup_agent.sh с VPS)
- /bot/agents_awg/all        — список агентов (токены замаскированы)
- /bot/agents_awg/delete     — удалить агент (сервер выведен из эксплуатации)
- /bot/user_awg_configs/invalidate — инвалидация кэша конфигов
  (вызывается cleanup-режимом агента ПЕРЕД удалением неактивных пиров,
  чтобы юзерам не отдавался мёртвый конфиг из кэша)
"""

import logging

from fastapi import APIRouter, Request

from src.db.v3.awg.agent_pojo import AgentPojo
from src.db.v3.awg.user_config_pojo import UserConfigPojo
from src.utils.awg_provisioner import invalidate_agents_cache

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/vpn/api/v1/bot/agents_awg/register")
async def register_agent(request: Request):
    try:
        data = await request.json()
        ip_address = str(data.get("ip_address", "")).strip()
        token = str(data.get("token", "")).strip()
        if not ip_address or not token:
            return {"success": 0, "message": "ip_address and token required"}

        agent = AgentPojo()
        agent.ip_address = ip_address
        agent.token = token
        try:
            agent.port = int(data.get("port", 39744))
        except Exception:
            agent.port = 39744
        agent.scheme = str(data.get("scheme", "https")).strip() or "https"
        agent.enabled = True
        await agent.upsert()
        invalidate_agents_cache()
        logger.info(f"AWG agent registered: {ip_address}:{agent.port}")
        return {"success": 1, "message": "registered"}
    except Exception as e:
        logger.error(f"Error registering AWG agent: {e}")
        return {"success": 0, "message": str(e)}


@router.get("/vpn/api/v1/bot/agents_awg/all")
async def get_all_agents():
    try:
        agents = await AgentPojo.find_all()
        return {"success": 1, "data": [a.to_public_doc() for a in agents]}
    except Exception as e:
        logger.error(f"Error fetching AWG agents: {e}")
        return {"success": 0, "message": str(e)}


@router.post("/vpn/api/v1/bot/agents_awg/delete")
async def delete_agent(request: Request):
    try:
        data = await request.json()
        ip_address = str(data.get("ip_address", "")).strip()
        if not ip_address:
            return {"success": 0, "message": "ip_address required"}
        await AgentPojo.delete_by_ip(ip_address)
        deleted = await UserConfigPojo.delete_by_server(ip_address)
        invalidate_agents_cache()
        logger.info(f"AWG agent deleted: {ip_address}, configs invalidated: {deleted}")
        return {"success": 1, "message": "deleted", "configs_invalidated": deleted}
    except Exception as e:
        logger.error(f"Error deleting AWG agent: {e}")
        return {"success": 0, "message": str(e)}


@router.post("/vpn/api/v1/bot/user_awg_configs/invalidate")
async def invalidate_user_configs(request: Request):
    try:
        data = await request.json()
        ip_address = str(data.get("ip_address", "")).strip()
        if not ip_address:
            return {"success": 0, "message": "ip_address required"}

        if data.get("all"):
            deleted = await UserConfigPojo.delete_by_server(ip_address)
        else:
            names = data.get("names", [])
            if not isinstance(names, list) or not names:
                return {"success": 0, "message": "names list required (or all=true)"}
            names = [str(n) for n in names][:10000]
            deleted = await UserConfigPojo.delete_by_peer_names(ip_address, names)

        logger.info(f"AWG user configs invalidated for {ip_address}: {deleted}")
        return {"success": 1, "deleted": deleted}
    except Exception as e:
        logger.error(f"Error invalidating AWG user configs: {e}")
        return {"success": 0, "message": str(e)}
