"""
Выдача персональных AmneziaWG-конфигов (по одному peer на пользователя).

Логика для каждой пары (user_id, сервер):
  1. Кэш в Mongo (awg_user_configs) — если есть, отдаём мгновенно.
  2. Иначе просим агент на VPS создать peer (POST /v1/peer), кэшируем, отдаём.
  3. Если агент недоступен / не зарегистрирован — возвращаем None,
     и endpoint отдаёт старый общий конфиг сервера (graceful degradation).

Зачем: общий конфиг на всех юзеров ломает сервер (replay-защита WireGuard:
устройство со сбитыми вперёд часами блокирует handshake всем остальным).
"""

import asyncio
import logging
import time

import httpx

from src.db.v3.awg.agent_pojo import AgentPojo
from src.db.v3.awg.user_config_pojo import UserConfigPojo

logger = logging.getLogger(__name__)

AGENT_REQUEST_TIMEOUT = 4.0   # сек на один вызов агента
TOTAL_PROVISION_TIMEOUT = 6.0  # сек на все серверы суммарно (gather)
AGENT_FAIL_COOLDOWN = 60.0    # сек не дёргать агент после ошибки

# ip_address -> unix time последней ошибки агента (in-memory negative cache)
_agent_failures: dict[str, float] = {}

# Кэш списка агентов, чтобы не ходить в Mongo на каждый запрос списка серверов
_agents_cache: dict[str, AgentPojo] = {}
_agents_cache_at: float = 0.0
AGENTS_CACHE_TTL = 30.0


async def _get_agents() -> dict[str, AgentPojo]:
    global _agents_cache, _agents_cache_at
    now = time.monotonic()
    if now - _agents_cache_at > AGENTS_CACHE_TTL:
        try:
            agents = await AgentPojo.find_all()
            _agents_cache = {a.ip_address: a for a in agents if a.enabled and a.token}
            _agents_cache_at = now
        except Exception as e:
            logger.error(f"awg_provisioner: cannot load agents: {e}")
    return _agents_cache


def invalidate_agents_cache():
    global _agents_cache_at
    _agents_cache_at = 0.0


async def _call_agent(agent: AgentPojo, user_id: str) -> dict | None:
    url = f"{agent.scheme}://{agent.ip_address}:{agent.port}/v1/peer"
    try:
        async with httpx.AsyncClient(verify=False, timeout=AGENT_REQUEST_TIMEOUT) as client:
            resp = await client.post(
                url,
                json={"user_id": user_id},
                headers={"X-Auth-Token": agent.token},
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("success") == 1 and data.get("config"):
                return data
            logger.warning(
                f"awg_provisioner: agent {agent.ip_address} returned "
                f"status={resp.status_code} body={str(data)[:200]}"
            )
    except Exception as e:
        logger.warning(f"awg_provisioner: agent {agent.ip_address} unreachable: {e}")
    return None


async def get_personal_config(user_id: str, server_ip: str) -> str | None:
    """Персональный конфиг (base64) для user_id на сервере server_ip, либо None."""
    # 1) Кэш
    try:
        cached = await UserConfigPojo.find_one(user_id, server_ip)
        if cached and cached.config:
            return cached.config
    except Exception as e:
        logger.error(f"awg_provisioner: cache lookup failed for {server_ip}: {e}")

    # 2) Агент
    agents = await _get_agents()
    agent = agents.get(server_ip)
    if agent is None:
        return None  # на этом сервере агент (ещё) не установлен

    last_fail = _agent_failures.get(server_ip, 0.0)
    if time.monotonic() - last_fail < AGENT_FAIL_COOLDOWN:
        return None  # недавно падал — не задерживаем ответ юзеру

    data = await _call_agent(agent, user_id)
    if data is None:
        _agent_failures[server_ip] = time.monotonic()
        return None
    _agent_failures.pop(server_ip, None)

    # 3) Кэшируем
    try:
        entry = UserConfigPojo()
        entry.user_id = user_id
        entry.ip_address = server_ip
        entry.peer_name = data.get("name", "")
        entry.config = data["config"]
        await entry.upsert()
    except Exception as e:
        logger.error(f"awg_provisioner: cache write failed for {server_ip}: {e}")

    return data["config"]


async def get_personal_configs(user_id: str, server_ips: list[str]) -> dict[str, str]:
    """
    Персональные конфиги для списка серверов параллельно.
    Возвращает {server_ip: config_b64} только для успешных. Никогда не бросает.
    """
    if not server_ips:
        return {}
    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                *[get_personal_config(user_id, ip) for ip in server_ips],
                return_exceptions=True,
            ),
            timeout=TOTAL_PROVISION_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("awg_provisioner: total provisioning timeout, serving fallback configs")
        return {}
    except Exception as e:
        logger.error(f"awg_provisioner: unexpected error: {e}")
        return {}

    configs: dict[str, str] = {}
    for ip, res in zip(server_ips, results):
        if isinstance(res, str) and res:
            configs[ip] = res
        elif isinstance(res, Exception):
            logger.error(f"awg_provisioner: error for {ip}: {res}")
    return configs
