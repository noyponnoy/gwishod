import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.db.v1.user_pojo import UserPojo, UserJson
from src.db.v1.server_pojo import ServerPojo, ServerJson
from src.db.v1.invoice_pojo import InvoicePojo, InvoiceJson
from src.db.v2.tariff_pojo import TariffPojo
from src.utils.crypto_user import mnemonic_to_device_id
from src.utils.platform import PLATFORM_UNKNOWN, normalize_platform

logger = logging.getLogger(__name__)

router = APIRouter()

DATE_FORMAT = "%a %b %d %H:%M:%S %Z %Y"


def _fmt(dt) -> str:
    if isinstance(dt, datetime):
        return dt.strftime(DATE_FORMAT)
    return str(dt)


def _user_list_fields(u: UserPojo) -> dict:
    """Общие поля юзера для списка / поиска / карточки (панель + бот)."""
    return {
        "id": u.id,
        "email": u.email,
        "isAnonymous": u.is_anonymous,
        "isPremium": u.is_premium,
        "premiumEnd": _fmt(u.premium_end),
        "createdAt": _fmt(u.created_at),
        "lastLogin": _fmt(u.last_login),
        "totalUpload": u.total_upload,
        "totalDownload": u.total_download,
        "countryCode": u.country_code,
        "deviceId": u.device_id,
        "platform": normalize_platform(getattr(u, "platform", PLATFORM_UNKNOWN)),
        "bundleId": getattr(u, "bundle_id", "") or "",
        "firstPlatform": normalize_platform(
            getattr(u, "first_platform", PLATFORM_UNKNOWN)
        ),
    }


def _empty_platform_bucket() -> dict:
    return {
        "total": 0,
        "premium": 0,
        "free": 0,
        "new24h": 0,
        "active24h": 0,
        "onlineNow": 0,
        "onlinePremium": 0,
        "onlineFree": 0,
    }


# ─── USERS ─────────────────────────────────────

@router.get("/vpn/api/v1/bot/users/all")
async def bot_get_all_users(skip: int = 0, limit: int = 20, platform: str = ""):
    """Список юзеров. platform=android|ios|unknown — опциональный фильтр."""
    all_users = await UserPojo.find_all()
    plat = normalize_platform(platform) if platform else ""
    if platform and plat in ("android", "ios", "unknown"):
        all_users = [
            u for u in all_users
            if normalize_platform(getattr(u, "platform", PLATFORM_UNKNOWN)) == plat
        ]
    total = len(all_users)
    page = all_users[skip:skip + limit]
    data = [_user_list_fields(u) for u in page]
    return {"success": 1, "total": total, "skip": skip, "limit": limit, "data": data}


@router.get("/vpn/api/v1/bot/users/search")
async def bot_search_user(q: str = "", platform: str = ""):
    if not q:
        return {"success": 0, "message": "query required", "data": []}
    all_users = await UserPojo.find_all()
    results = []
    q_lower = q.lower()
    plat = normalize_platform(platform) if platform else ""
    for u in all_users:
        if q_lower in u.id.lower() or q_lower in u.email.lower() or q_lower in u.device_id.lower():
            if platform and plat in ("android", "ios", "unknown"):
                if normalize_platform(getattr(u, "platform", PLATFORM_UNKNOWN)) != plat:
                    continue
            results.append(_user_list_fields(u))
    return {"success": 1, "total": len(results), "data": results}


@router.get("/vpn/api/v1/bot/users/get")
async def bot_get_user(device_id: str = ""):
    if not device_id:
        return {"success": 0, "message": "device_id required", "data": {}}
    user = UserPojo()
    user.device_id = device_id
    user = await user.find()
    if user is None:
        return {"success": 0, "message": "user not found", "data": {}}
    invoices = InvoicePojo()
    invoices.user_id = user.id
    inv_list = await invoices.find_all_by_user_id()
    inv_data = []
    for inv in inv_list:
        inv_data.append({
            "invoiceId": inv.invoice_id,
            "amount": inv.amount,
            "status": str(inv.status),
            "plan": inv.plan,
            "created": _fmt(inv.created),
        })
    data = _user_list_fields(user)
    data["sourceIp"] = user.source_ip
    data["invoices"] = inv_data
    pua = getattr(user, "platform_updated_at", None)
    data["platformUpdatedAt"] = _fmt(pua) if pua else ""
    return {
        "success": 1,
        "data": data,
    }


@router.post("/vpn/api/v1/bot/users/premium/set")
async def bot_set_premium(request: Request):
    body = await request.body()
    params: dict[str, str] = {}
    for pair in body.decode("utf-8").split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            params[parts[0]] = parts[1]
    device_id = params.get("deviceId", "").strip()
    days = params.get("days", "30").strip()
    if not device_id:
        return {"success": 0, "message": "deviceId required"}
    user = UserPojo()
    user.device_id = device_id
    user = await user.find()
    if user is None:
        return {"success": 0, "message": "user not found"}
    try:
        days_int = int(days)
    except ValueError:
        days_int = 30
    user.is_premium = True
    user.premium_end = datetime.now(timezone.utc) + timedelta(days=days_int)
    await user.update()
    return {"success": 1, "message": f"Premium set for {days_int} days", "premiumEnd": _fmt(user.premium_end)}


@router.post("/vpn/api/v1/bot/users/premium/revoke")
async def bot_revoke_premium(request: Request):
    body = await request.body()
    params: dict[str, str] = {}
    for pair in body.decode("utf-8").split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            params[parts[0]] = parts[1]
    device_id = params.get("deviceId", "").strip()
    if not device_id:
        return {"success": 0, "message": "deviceId required"}
    user = UserPojo()
    user.device_id = device_id
    user = await user.find()
    if user is None:
        return {"success": 0, "message": "user not found"}
    user.is_premium = False
    user.premium_end = datetime(2000, 1, 1, tzinfo=timezone.utc)
    await user.update()
    return {"success": 1, "message": "Premium revoked"}


# ─── ANALYTICS ─────────────────────────────────

def _ensure_aware(dt):
    if isinstance(dt, datetime) and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@router.get("/vpn/api/v1/bot/analytics/summary")
async def bot_analytics_summary():
    """Сводка + byPlatform. find_all был и раньше — не добавляем heartbeat-нагрузку."""
    all_users = await UserPojo.find_all()
    total = len(all_users)
    premium = sum(1 for u in all_users if u.is_premium)
    free = total - premium
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    five_min_ago = now - timedelta(minutes=5)
    new_24h = sum(1 for u in all_users if _ensure_aware(u.created_at) >= day_ago)
    active_24h = sum(1 for u in all_users if _ensure_aware(u.last_login) >= day_ago)
    online_now = sum(1 for u in all_users if _ensure_aware(u.last_login) >= five_min_ago)
    online_premium = sum(1 for u in all_users if u.is_premium and _ensure_aware(u.last_login) >= five_min_ago)
    online_free = online_now - online_premium

    # Разбивка по platform (старые поля summary сохранены для совместимости)
    by_platform = {
        "android": _empty_platform_bucket(),
        "ios": _empty_platform_bucket(),
        "unknown": _empty_platform_bucket(),
    }
    for u in all_users:
        key = normalize_platform(getattr(u, "platform", PLATFORM_UNKNOWN))
        if key not in by_platform:
            key = "unknown"
        b = by_platform[key]
        b["total"] += 1
        if u.is_premium:
            b["premium"] += 1
        else:
            b["free"] += 1
        if _ensure_aware(u.created_at) >= day_ago:
            b["new24h"] += 1
        if _ensure_aware(u.last_login) >= day_ago:
            b["active24h"] += 1
        if _ensure_aware(u.last_login) >= five_min_ago:
            b["onlineNow"] += 1
            if u.is_premium:
                b["onlinePremium"] += 1
            else:
                b["onlineFree"] += 1

    return {
        "success": 1,
        "data": {
            "total": total,
            "premium": premium,
            "free": free,
            "new24h": new_24h,
            "active24h": active_24h,
            "onlineNow": online_now,
            "onlinePremium": online_premium,
            "onlineFree": online_free,
            "byPlatform": by_platform,
        },
    }


# ─── SERVERS ───────────────────────────────────

@router.get("/vpn/api/v1/bot/servers/all")
async def bot_get_all_servers():
    servers = await ServerPojo.find_all()
    data = []
    for s in servers:
        data.append({
            "id": s.ip_address,
            "country": s.country,
            "countryCode": s.country_code,
            "ipAddress": s.ip_address,
            "premium": s.premium,
            "status": s.status,
            "state": s.state,
            "recommend": s.recommend,
            "priority": s.priority,
        })
    return {"success": 1, "total": len(data), "data": data}


@router.get("/vpn/api/v1/bot/servers/get")
async def bot_get_server(ip_address: str = ""):
    if not ip_address:
        return {"success": 0, "message": "ip_address required"}
    servers = await ServerPojo.find_all()
    for s in servers:
        if s.ip_address == ip_address:
            return {
                "success": 1,
                "data": {
                    "ipAddress": s.ip_address,
                    "country": s.country,
                    "countryCode": s.country_code,
                    "state": s.state,
                    "premium": s.premium,
                    "status": s.status,
                    "recommend": s.recommend,
                    "priority": s.priority,
                    "u_nsm": s.u_nsm,
                    "p_nsm": s.p_nsm,
                    "caFileName": s.ca_file_name,
                    "caFile": s.ca_file,
                },
            }
    return {"success": 0, "message": "server not found"}


@router.post("/vpn/api/v1/bot/servers/create")
async def bot_create_server(request: Request):
    body = await request.body()
    params: dict[str, str] = {}
    for pair in body.decode("utf-8").split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            from urllib.parse import unquote_plus
            params[unquote_plus(parts[0])] = unquote_plus(parts[1])

    ip_address = params.get("ipAddress", "").strip()
    if not ip_address:
        return {"success": 0, "message": "ipAddress is required"}

    all_servers = await ServerPojo.find_all()
    for s in all_servers:
        if s.ip_address == ip_address:
            return {"success": 0, "message": f"server {ip_address} already exists"}

    server = ServerPojo()
    server.ip_address = ip_address
    server.id = params.get("_id", ip_address)
    server.country = params.get("country", "")
    server.country_code = params.get("countryCode", "")
    server.state = params.get("state", "")
    server.u_nsm = params.get("u_nsm", "")
    server.p_nsm = params.get("p_nsm", "")
    server.ca_file_name = params.get("caFileName", "")
    server.ca_file = params.get("caFile", "")
    server.premium = params.get("premium", "false").lower() in ("true", "1")
    server.status = params.get("status", "true").lower() in ("true", "1")
    server.recommend = params.get("recommend", "false").lower() in ("true", "1")
    try:
        server.priority = int(params.get("priority", "0"))
    except ValueError:
        server.priority = 0

    await server.insert()
    return {"success": 1, "message": "Server created"}


@router.post("/vpn/api/v1/bot/servers/update")
async def bot_update_server(request: Request):
    body = await request.body()
    params: dict[str, str] = {}
    for pair in body.decode("utf-8").split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            from urllib.parse import unquote_plus
            params[unquote_plus(parts[0])] = unquote_plus(parts[1])

    ip_address = params.get("ipAddress", "").strip()
    if not ip_address:
        return {"success": 0, "message": "ipAddress is required"}

    all_servers = await ServerPojo.find_all()
    server = None
    for s in all_servers:
        if s.ip_address == ip_address:
            server = s
            break

    if server is None:
        return {"success": 0, "message": "server not found"}

    if "country" in params:
        server.country = params["country"]
    if "countryCode" in params:
        server.country_code = params["countryCode"]
    if "state" in params:
        server.state = params["state"]
    if "u_nsm" in params:
        server.u_nsm = params["u_nsm"]
    if "p_nsm" in params:
        server.p_nsm = params["p_nsm"]
    if "caFileName" in params:
        server.ca_file_name = params["caFileName"]
    if "caFile" in params:
        server.ca_file = params["caFile"]
    if "premium" in params:
        server.premium = params["premium"].lower() in ("true", "1")
    if "status" in params:
        server.status = params["status"].lower() in ("true", "1")
    if "recommend" in params:
        server.recommend = params["recommend"].lower() in ("true", "1")
    if "priority" in params:
        try:
            server.priority = int(params["priority"])
        except ValueError:
            pass

    await server.update()
    return {"success": 1, "message": "Server updated"}


@router.post("/vpn/api/v1/bot/servers/delete")
async def bot_delete_server(request: Request):
    body = await request.body()
    params: dict[str, str] = {}
    for pair in body.decode("utf-8").split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            params[parts[0]] = parts[1]

    ip_address = params.get("ipAddress", "").strip()
    if not ip_address:
        return {"success": 0, "message": "ipAddress is required"}

    all_servers = await ServerPojo.find_all()
    for s in all_servers:
        if s.ip_address == ip_address:
            await s.delete()
            return {"success": 1, "message": "Server deleted"}

    return {"success": 0, "message": "server not found"}


@router.post("/vpn/api/v1/bot/servers/toggle")
async def bot_toggle_server(request: Request):
    body = await request.body()
    params: dict[str, str] = {}
    for pair in body.decode("utf-8").split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            params[parts[0]] = parts[1]

    ip_address = params.get("ipAddress", "").strip()
    if not ip_address:
        return {"success": 0, "message": "ipAddress is required"}

    all_servers = await ServerPojo.find_all()
    for s in all_servers:
        if s.ip_address == ip_address:
            s.status = not s.status
            await s.update()
            return {"success": 1, "message": f"Server {'enabled' if s.status else 'disabled'}"}

    return {"success": 0, "message": "server not found"}


# ─── SERVERS VLESS ─────────────────────────────

@router.get("/vpn/api/v1/bot/servers_vless/all")
async def bot_get_all_servers_vless():
    from src.db.v3.a3xui.server_pojo import ServerPojo as VlessServerPojo
    servers = await VlessServerPojo.find_all()
    data = []
    for s in servers:
        data.append({
            "server_ip": s.server_ip,
            "server_domain_port_path": s.server_domain_port_path,
            "server_domain_port_path_sub": s.server_domain_port_path_sub,
            "login": s.login,
            "password": s.password,
            "session": s.session,
            "t_name": s.t_name,
            "description": s.description,
        })
    return {"success": 1, "total": len(data), "data": data}

@router.get("/vpn/api/v1/bot/servers_vless/get")
async def bot_get_server_vless(server_ip: str = ""):
    from src.db.v3.a3xui.server_pojo import ServerPojo as VlessServerPojo
    if not server_ip:
        return {"success": 0, "message": "server_ip required"}
    servers = await VlessServerPojo.find_all()
    for s in servers:
        if s.server_ip == server_ip:
            return {
                "success": 1,
                "data": {
                    "server_ip": s.server_ip,
                    "server_domain_port_path": s.server_domain_port_path,
                    "server_domain_port_path_sub": s.server_domain_port_path_sub,
                    "login": s.login,
                    "password": s.password,
                    "session": s.session,
                    "t_name": s.t_name,
                    "description": s.description,
                }
            }
    return {"success": 0, "message": "server not found"}

@router.post("/vpn/api/v1/bot/servers_vless/create")
async def bot_create_server_vless(request: Request):
    from src.db.v3.a3xui.server_pojo import ServerPojo as VlessServerPojo
    body = await request.body()
    params: dict[str, str] = {}
    for pair in body.decode("utf-8").split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            from urllib.parse import unquote_plus
            params[unquote_plus(parts[0])] = unquote_plus(parts[1])

    server_ip = params.get("server_ip", "").strip()
    if not server_ip:
        return {"success": 0, "message": "server_ip is required"}

    all_servers = await VlessServerPojo.find_all()
    for s in all_servers:
        if s.server_ip == server_ip:
            return {"success": 0, "message": f"server {server_ip} already exists"}

    server = VlessServerPojo()
    server.server_ip = server_ip
    server.server_domain_port_path = params.get("server_domain_port_path", "0")
    server.server_domain_port_path_sub = params.get("server_domain_port_path_sub", "0")
    server.login = params.get("login", "0")
    server.password = params.get("password", "0")
    server.session = params.get("session", "0")
    server.description = params.get("description", "0")
    try:
        server.t_name = int(params.get("t_name", "0"))
    except ValueError:
        server.t_name = 0

    await server.insert()
    return {"success": 1, "message": "Server created"}

@router.post("/vpn/api/v1/bot/servers_vless/update")
async def bot_update_server_vless(request: Request):
    from src.db.v3.a3xui.server_pojo import ServerPojo as VlessServerPojo
    body = await request.body()
    params: dict[str, str] = {}
    for pair in body.decode("utf-8").split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            from urllib.parse import unquote_plus
            params[unquote_plus(parts[0])] = unquote_plus(parts[1])

    server_ip = params.get("server_ip", "").strip()
    if not server_ip:
        return {"success": 0, "message": "server_ip is required"}

    all_servers = await VlessServerPojo.find_all()
    server = None
    for s in all_servers:
        if s.server_ip == server_ip:
            server = s
            break

    if server is None:
        return {"success": 0, "message": "server not found"}

    if "server_domain_port_path" in params: server.server_domain_port_path = params["server_domain_port_path"]
    if "server_domain_port_path_sub" in params: server.server_domain_port_path_sub = params["server_domain_port_path_sub"]
    if "login" in params: server.login = params["login"]
    if "password" in params: server.password = params["password"]
    if "session" in params: server.session = params["session"]
    if "description" in params: server.description = params["description"]
    if "t_name" in params:
        try:
            server.t_name = int(params["t_name"])
        except ValueError:
            pass

    await server.update()
    return {"success": 1, "message": "Server updated"}

@router.post("/vpn/api/v1/bot/servers_vless/delete")
async def bot_delete_server_vless(request: Request):
    """Удаление VLESS-сервера из панели.

    Важно: body form-urlencoded — декодируем (иначе server_ip с ':'
    приходит как %3A и не находится → «server not found»).
    """
    from urllib.parse import unquote_plus
    from src.db.v3.a3xui.server_pojo import ServerPojo as VlessServerPojo

    body = await request.body()
    params: dict[str, str] = {}
    for pair in body.decode("utf-8").split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            params[unquote_plus(parts[0])] = unquote_plus(parts[1])

    server_ip = params.get("server_ip", "").strip()
    if not server_ip:
        return {"success": 0, "message": "server_ip is required"}

    all_servers = await VlessServerPojo.find_all()
    for s in all_servers:
        db_ip = (s.server_ip or "").strip()
        if not db_ip:
            continue
        # точное совпадение после URL-decode
        if db_ip == server_ip:
            await s.delete()
            return {"success": 1, "message": "Server deleted"}
        # domain:port vs domain — если один «расширяет» другой
        if db_ip == server_ip.split(":")[0] or server_ip == db_ip.split(":")[0]:
            await s.delete()
            return {"success": 1, "message": "Server deleted"}
        if db_ip.lower() == server_ip.lower():
            await s.delete()
            return {"success": 1, "message": "Server deleted"}

    return {
        "success": 0,
        "message": "server not found",
        "server_ip": server_ip,
        "known": [s.server_ip for s in all_servers],
    }

# ─── TARIFFS ───────────────────────────────────

@router.get("/vpn/api/v1/bot/tariffs/all")
async def bot_get_all_tariffs():
    tariffs = await TariffPojo.find_all()
    data = []
    for t in tariffs:
        data.append({
            "name": t.name,
            "technicalName": t.technical_name,
            "description": t.description,
            "price": t.price,
            "enabled": t.enabled,
            "duration": t.duration,
        })
    return {"success": 1, "total": len(data), "data": data}


@router.get("/vpn/api/v1/bot/tariffs/get")
async def bot_get_tariff(technical_name: str = ""):
    if not technical_name:
        return {"success": 0, "message": "technical_name required"}
    t = TariffPojo()
    t.technical_name = technical_name
    t = await t.find()
    if t is None:
        return {"success": 0, "message": "tariff not found"}
    return {
        "success": 1,
        "data": {
            "name": t.name,
            "technicalName": t.technical_name,
            "description": t.description,
            "price": t.price,
            "enabled": t.enabled,
            "duration": t.duration,
        },
    }


@router.post("/vpn/api/v1/bot/tariffs/create")
async def bot_create_tariff(request: Request):
    body = await request.body()
    params: dict[str, str] = {}
    for pair in body.decode("utf-8").split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            from urllib.parse import unquote_plus
            params[unquote_plus(parts[0])] = unquote_plus(parts[1])

    name = params.get("name", "").strip()
    technical_name = params.get("technicalName", "").strip()
    price = params.get("price", "0").strip()
    duration = params.get("duration", "0").strip()
    description = params.get("description", "").strip()
    enabled = params.get("enabled", "true").strip().lower() in ("true", "1")

    if not name or not technical_name:
        return {"success": 0, "message": "name and technicalName are required"}

    if await TariffPojo.is_exist(technical_name):
        return {"success": 0, "message": f"tariff '{technical_name}' already exists"}

    try:
        price_f = float(price)
    except ValueError:
        price_f = 0.0
    try:
        duration_i = int(duration)
    except ValueError:
        duration_i = 0

    tariff = TariffPojo()
    tariff.name = name
    tariff.technical_name = technical_name
    tariff.description = description
    tariff.price = price_f
    tariff.enabled = enabled
    tariff.duration = duration_i
    await tariff.insert()
    return {"success": 1, "message": "Tariff created"}


@router.post("/vpn/api/v1/bot/tariffs/update")
async def bot_update_tariff(request: Request):
    body = await request.body()
    params: dict[str, str] = {}
    for pair in body.decode("utf-8").split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            from urllib.parse import unquote_plus
            params[unquote_plus(parts[0])] = unquote_plus(parts[1])

    technical_name = params.get("technicalName", "").strip()
    if not technical_name:
        return {"success": 0, "message": "technicalName is required"}

    tmp = TariffPojo()
    tmp.technical_name = technical_name
    tariff = await tmp.find()
    if tariff is None:
        return {"success": 0, "message": "tariff not found"}

    if "name" in params:
        tariff.name = params["name"]
    if "price" in params:
        try:
            tariff.price = float(params["price"])
        except ValueError:
            pass
    if "duration" in params:
        try:
            tariff.duration = int(params["duration"])
        except ValueError:
            pass
    if "description" in params:
        tariff.description = params["description"]
    if "enabled" in params:
        tariff.enabled = params["enabled"].lower() in ("true", "1")

    await tariff.update()
    return {"success": 1, "message": "Tariff updated"}


@router.post("/vpn/api/v1/bot/tariffs/delete")
async def bot_delete_tariff(request: Request):
    body = await request.body()
    params: dict[str, str] = {}
    for pair in body.decode("utf-8").split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            params[parts[0]] = parts[1]

    technical_name = params.get("technicalName", "").strip()
    if not technical_name:
        return {"success": 0, "message": "technicalName is required"}

    tariff = TariffPojo()
    tariff.technical_name = technical_name
    tariff = await tariff.find()
    if tariff is None:
        return {"success": 0, "message": "tariff not found"}

    await tariff.delete()
    return {"success": 1, "message": "Tariff deleted"}


# ─── INVOICES ──────────────────────────────────

@router.get("/vpn/api/v1/bot/invoices/all")
async def bot_get_all_invoices(skip: int = 0, limit: int = 20):
    collection = await InvoicePojo.get_collection()
    total = await collection.count_documents({})
    cursor = collection.find({}).sort("created", -1).skip(skip).limit(limit)
    data = []
    async for doc in cursor:
        data.append({
            "invoiceId": doc.get("invoiceId", ""),
            "userId": doc.get("userId", ""),
            "amount": doc.get("amount", ""),
            "currency": doc.get("currency", ""),
            "status": doc.get("status", ""),
            "plan": doc.get("plan", ""),
            "payUrl": doc.get("payUrl", ""),
            "created": str(doc.get("created", "")),
            "updated": str(doc.get("updated", "")),
            "FKoperationId": doc.get("FKoperationId", ""),
            "P_EMAIL": doc.get("P_EMAIL", ""),
            "P_PHONE": doc.get("P_PHONE", ""),
            "payerAccount": doc.get("payerAccount", ""),
            "commission": doc.get("commission", ""),
        })
    return {"success": 1, "total": total, "skip": skip, "limit": limit, "data": data}


# ─── SEARCH BY MNEMONIC ───────────────────────

@router.get("/vpn/api/v1/bot/users/search_by_mnemonic")
async def bot_search_by_mnemonic(mnemonic: str = ""):
    if not mnemonic:
        return {"success": 0, "message": "mnemonic required", "data": {}}
    device_id = mnemonic_to_device_id(mnemonic.strip())
    if device_id is None:
        return {"success": 0, "message": "invalid mnemonic", "data": {}}

    all_users = await UserPojo.find_all()
    for u in all_users:
        if u.device_id == device_id:
            invoices = InvoicePojo()
            invoices.user_id = u.id
            inv_list = await invoices.find_all_by_user_id()
            inv_data = []
            for inv in inv_list:
                inv_data.append({
                    "invoiceId": inv.invoice_id,
                    "amount": inv.amount,
                    "status": str(inv.status),
                    "plan": inv.plan,
                    "created": _fmt(inv.created),
                })
            return {
                "success": 1,
                "data": {
                    "id": u.id,
                    "email": u.email,
                    "isAnonymous": u.is_anonymous,
                    "isPremium": u.is_premium,
                    "premiumEnd": _fmt(u.premium_end),
                    "createdAt": _fmt(u.created_at),
                    "lastLogin": _fmt(u.last_login),
                    "totalUpload": u.total_upload,
                    "totalDownload": u.total_download,
                    "countryCode": u.country_code,
                    "deviceId": u.device_id,
                    "sourceIp": u.source_ip,
                    "invoices": inv_data,
                },
            }
    return {"success": 0, "message": "user not found by mnemonic", "data": {}, "deviceId": device_id}
