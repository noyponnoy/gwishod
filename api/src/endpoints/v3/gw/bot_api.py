"""GW bot admin API — CRUD endpoints for the Telegram bot / web panel.

Mirrors api/src/endpoints/v3/awg/bot_api.py: raw Request body parsing (no Pydantic
in signatures, matching the repo convention), paths under /vpn/api/v1/bot/servers_gw/*.

Every handler returns a plain dict that FastAPI serializes to JSON.
"""
from fastapi import APIRouter, Request, HTTPException

from src.db.v3.gw.server_pojo import ServerPojo

router = APIRouter()

# fields the bot/panel is allowed to set on create/update
_ALLOWED_FIELDS = {
    "name", "ip_address", "ssh_port", "ssh_username", "ssh_password",
    "proxy_host", "proxy_port", "proxy_scheme", "payload", "sni",
    "country", "country_code", "state", "premium", "recommend",
    "priority", "status", "ssh_hostkey",
}


def _bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("1", "true", "yes", "on", "y")
    return bool(v)


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


@router.get("/vpn/api/v1/bot/servers_gw/all")
async def bot_get_all_servers_gw():
    servers = await ServerPojo.find_all()
    return {"ok": True, "servers": [s.to_doc() for s in servers], "count": len(servers)}


@router.get("/vpn/api/v1/bot/servers_gw/get")
async def bot_get_server_gw(server_ip: str):
    s = await ServerPojo.find(server_ip)
    if not s:
        raise HTTPException(status_code=404, detail="GW server not found")
    return {"ok": True, "server": s.to_doc()}


@router.post("/vpn/api/v1/bot/servers_gw/create")
async def bot_create_server_gw(request: Request):
    body = await request.json()
    ip = (body.get("ip_address") or "").strip()
    if not ip:
        raise HTTPException(status_code=400, detail="ip_address is required")
    if await ServerPojo.is_exist(ip):
        raise HTTPException(status_code=409, detail="GW server already exists")

    s = ServerPojo(ip_address=ip)
    for f in _ALLOWED_FIELDS:
        if f in body and body[f] is not None:
            v = body[f]
            if f in ("premium", "recommend", "status"):
                setattr(s, f, _bool(v))
            elif f in ("ssh_port", "proxy_port", "priority"):
                setattr(s, f, _int(v))
            else:
                setattr(s, f, v)
    s.id = s.id or ip
    await s.insert()
    return {"ok": True, "server": s.to_doc()}


@router.post("/vpn/api/v1/bot/servers_gw/update")
async def bot_update_server_gw(request: Request):
    body = await request.json()
    ip = (body.get("ip_address") or "").strip()
    if not ip:
        raise HTTPException(status_code=400, detail="ip_address is required")
    s = await ServerPojo.find(ip)
    if not s:
        raise HTTPException(status_code=404, detail="GW server not found")

    changed = []
    for f in _ALLOWED_FIELDS:
        if f in body and body[f] is not None and f != "ip_address":
            v = body[f]
            if f in ("premium", "recommend", "status"):
                if getattr(s, f) != _bool(v):
                    setattr(s, f, _bool(v)); changed.append(f)
            elif f in ("ssh_port", "proxy_port", "priority"):
                if getattr(s, f) != _int(v):
                    setattr(s, f, _int(v)); changed.append(f)
            else:
                if str(getattr(s, f)) != str(v):
                    setattr(s, f, v); changed.append(f)
    await s.update()
    return {"ok": True, "server": s.to_doc(), "changed": changed}


@router.post("/vpn/api/v1/bot/servers_gw/delete")
async def bot_delete_server_gw(request: Request):
    body = await request.json()
    ip = (body.get("ip_address") or "").strip()
    if not ip:
        raise HTTPException(status_code=400, detail="ip_address is required")
    res = await ServerPojo.delete_by_ip(ip)
    return {"ok": True, "deleted": res.deleted_count, "ip_address": ip}
