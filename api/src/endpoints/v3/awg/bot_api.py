from fastapi import APIRouter, Request
from src.db.v3.awg.server_pojo import ServerPojo
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/vpn/api/v1/bot/servers_awg/all")
async def bot_get_all_servers_awg():
    try:
        servers = await ServerPojo.find_all()
        return {"success": 1, "data": [s.to_doc() for s in servers]}
    except Exception as e:
        logger.error(f"Error fetching all AWG servers: {e}")
        return {"success": 0, "message": str(e)}

@router.get("/vpn/api/v1/bot/servers_awg/get")
async def bot_get_server_awg(server_ip: str = ""):
    if not server_ip:
        return {"success": 0, "message": "server_ip required"}
    try:
        server = ServerPojo()
        server.ip_address = server_ip
        found = await server.find()
        if not found:
            return {"success": 0, "message": "not found"}
        return {"success": 1, "data": found.to_doc()}
    except Exception as e:
        logger.error(f"Error fetching AWG server: {e}")
        return {"success": 0, "message": str(e)}

@router.post("/vpn/api/v1/bot/servers_awg/create")
async def bot_create_server_awg(request: Request):
    try:
        data = await request.json()
        server_ip = data.get("ip_address")
        if not server_ip:
            return {"success": 0, "message": "ip_address required"}

        server = ServerPojo()
        server.ip_address = server_ip
        server.country = data.get("country", "")
        server.state = data.get("state", "")
        server.country_code = data.get("country_code", "")
        server.recommend = data.get("recommend", False)
        server.priority = data.get("priority", 0)
        server.config = data.get("config", "")
        server.premium = data.get("premium", False)
        server.status = data.get("status", False)
        
        await server.insert()
        return {"success": 1, "message": "created"}
    except Exception as e:
        logger.error(f"Error creating AWG server: {e}")
        return {"success": 0, "message": str(e)}

@router.post("/vpn/api/v1/bot/servers_awg/update")
async def bot_update_server_awg(request: Request):
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)

        def _to_str(value, default=""):
            if value is None:
                return default
            return str(value)

        def _to_bool(value, default=False):
            if isinstance(value, bool):
                return value
            if value is None:
                return default
            return str(value).strip().lower() in ("1", "true", "yes", "on")

        def _to_int(value, default=0):
            try:
                return int(value)
            except Exception:
                return default

        server_ip = _to_str(data.get("ip_address"), "")
        if not server_ip:
            server_ip = _to_str(data.get("ipAddress"), "")
        server_ip = server_ip.strip()
        if not server_ip:
            return {"success": 0, "message": "ip_address required"}

        server = ServerPojo()
        server.ip_address = server_ip
        found = await server.find()
        if not found:
            return {"success": 0, "message": "not found"}

        if "country" in data:
            found.country = _to_str(data["country"], found.country)
        if "state" in data:
            found.state = _to_str(data["state"], found.state)
        if "country_code" in data:
            found.country_code = _to_str(data["country_code"], found.country_code)
        elif "countryCode" in data:
            found.country_code = _to_str(data["countryCode"], found.country_code)
        if "recommend" in data:
            found.recommend = _to_bool(data["recommend"], found.recommend)
        if "priority" in data:
            found.priority = _to_int(data["priority"], found.priority)
        if "config" in data:
            found.config = _to_str(data["config"], found.config)
        if "premium" in data:
            found.premium = _to_bool(data["premium"], found.premium)
        if "status" in data:
            found.status = _to_bool(data["status"], found.status)

        await found.update()
        return {"success": 1, "message": "updated"}
    except Exception as e:
        logger.error(f"Error updating AWG server: {e}")
        return {"success": 0, "message": str(e)}

@router.post("/vpn/api/v1/bot/servers_awg/delete")
async def bot_delete_server_awg(request: Request):
    try:
        data = await request.json()
        server_ip = data.get("ip_address")
        if not server_ip:
            return {"success": 0, "message": "ip_address required"}
            
        server = ServerPojo()
        server.ip_address = server_ip
        await server.delete()
        return {"success": 1, "message": "deleted"}
    except Exception as e:
        logger.error(f"Error deleting AWG server: {e}")
        return {"success": 0, "message": str(e)}
