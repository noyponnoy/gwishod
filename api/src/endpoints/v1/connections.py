import asyncio
import hashlib
import logging
import time as time_module
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl

from fastapi import APIRouter, Request
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

router = APIRouter()

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "active_connections"

# ── Параметры учёта ──────────────────────────────────────────────────────────
# Сколько минут без heartbeat юзер считается онлайн.
# Прила шлёт heartbeat раз в 60 сек; 5 минут = терпим до 4 пропусков
# (Doze, плохая сеть, фоновые ограничения Android).
ONLINE_WINDOW_MINUTES = 5
# Через сколько секунд Mongo сама удаляет неактивные документы (TTL-индекс).
# Должно быть заметно больше ONLINE_WINDOW_MINUTES.
TTL_EXPIRE_SECONDS = 900  # 15 минут
# Грейс после disconnect: «опоздавший» heartbeat, прилетевший в течение этого
# времени после disconnect, НЕ воскрешает юзера (защита от гонки
# disconnect -> застрявший в полёте heartbeat -> юзер-призрак).
DISCONNECT_GRACE_SECONDS = 90
# Кэш ответа /bot/servers/stats (бот автообновляется каждые 3 сек).
STATS_CACHE_SECONDS = 2.5
# Подпись запросов: прила (ModifyRequestInterceptor) добавляет к каждому POST
# поля hash/time, где hash = sha256("{time}|" + APP_SIGN_SECRET).
APP_SIGN_SECRET = "strongVPN!@#"

# ── Один общий Mongo-клиент на процесс (вместо нового на каждый запрос) ──────
_mongo_client: AsyncIOMotorClient | None = None
_indexes_ready = False
_indexes_lock = asyncio.Lock()


def _get_client() -> AsyncIOMotorClient:
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = AsyncIOMotorClient(MONGODB_URI, maxPoolSize=50)
    return _mongo_client


async def _ensure_indexes(collection) -> None:
    """Создаёт индексы один раз за время жизни процесса."""
    global _indexes_ready
    if _indexes_ready:
        return
    async with _indexes_lock:
        if _indexes_ready:
            return
        # 1) Уникальный индекс по userId (документ на юзера ровно один).
        #    Если в коллекции исторически остались дубли — чистим, оставляя
        #    самый свежий по lastSeen.
        try:
            await collection.create_index("userId", unique=True, name="userId_unique")
        except Exception as e:
            logger.warning(f"active_connections: userId index failed ({e}), deduping...")
            try:
                pipeline = [
                    {"$sort": {"lastSeen": -1}},
                    {"$group": {"_id": "$userId", "keep": {"$first": "$_id"}}},
                ]
                keep_ids = {doc["keep"] async for doc in collection.aggregate(pipeline)}
                await collection.delete_many({"_id": {"$nin": list(keep_ids)}})
                await collection.create_index("userId", unique=True, name="userId_unique")
            except Exception as e2:
                logger.error(f"active_connections: dedupe/index retry failed: {e2}")
        # 2) TTL-индекс: Mongo сама удаляет давно молчащие документы.
        #    Никаких delete_many в эндпоинте статистики больше нет.
        try:
            await collection.create_index(
                "lastSeen",
                expireAfterSeconds=TTL_EXPIRE_SECONDS,
                name="lastSeen_ttl",
            )
        except Exception as e:
            # Индекс мог быть создан раньше с другим expireAfterSeconds — обновляем.
            logger.warning(f"active_connections: TTL index create failed ({e}), recreating...")
            try:
                await collection.drop_index("lastSeen_ttl")
            except Exception:
                pass
            try:
                await collection.create_index(
                    "lastSeen",
                    expireAfterSeconds=TTL_EXPIRE_SECONDS,
                    name="lastSeen_ttl",
                )
            except Exception as e2:
                logger.error(f"active_connections: TTL index retry failed: {e2}")
        _indexes_ready = True


async def _get_collection():
    collection = _get_client()[DB_NAME][COLLECTION_NAME]
    await _ensure_indexes(collection)
    return collection


def _normalize_protocol(value: str) -> str:
    protocol = (value or "").strip().lower()
    if protocol in ("awg", "amneziawg", "amnezia_wg", "amnezia-wg"):
        return "awg"
    if protocol == "vless":
        return "vless"
    return "ikev2"


def _parse_form(body: bytes) -> dict[str, str]:
    """Корректный разбор form-urlencoded тела (с URL-декодированием)."""
    try:
        return dict(parse_qsl(body.decode("utf-8"), keep_blank_values=True))
    except Exception:
        return {}


def _signature_valid(params: dict[str, str]) -> bool:
    """Проверяет подпись, которую прила добавляет к каждому POST.

    ModifyRequestInterceptor в APK шлёт hash = sha256("{unixtime}|strongVPN!@#")
    и сам unixtime в поле time. Окно времени специально не проверяем жёстко:
    у части устройств сильно сбиты часы (это уже ловили на AWG), а подпись
    и без окна доказывает знание секрета.
    """
    sig_hash = params.get("hash", "").strip().lower()
    sig_time = params.get("time", "").strip()
    if not sig_hash or not sig_time:
        return False
    expected = hashlib.sha256(f"{sig_time}|{APP_SIGN_SECRET}".encode()).hexdigest()
    return sig_hash == expected


@router.post("/vpn/api/v1/user/connection/update")
async def update_connection(request: Request):
    body = await request.body()
    params = _parse_form(body)

    user_id = params.get("userId", "").strip()
    server_ip = params.get("serverIp", "").strip()
    protocol = _normalize_protocol(params.get("protocol", "ikev2"))
    action = params.get("action", "connect").strip()
    signed = _signature_valid(params)

    if not user_id:
        return {"success": 0, "message": "userId required"}

    if action in ("connect", "heartbeat") and not server_ip:
        return {"success": 0, "message": "serverIp required for connect/heartbeat"}

    collection = await _get_collection()
    now = datetime.now(timezone.utc)

    if action == "connect":
        if not signed:
            logger.warning(f"connection/update: unsigned connect from userId={user_id}")
        await collection.update_one(
            {"userId": user_id},
            {
                "$set": {
                    "userId": user_id,
                    "serverIp": server_ip,
                    "protocol": protocol,
                    "connectedAt": now,
                    "lastSeen": now,
                    "signed": signed,
                },
                "$unset": {"disconnectedAt": ""},
            },
            upsert=True,
        )

    elif action == "disconnect":
        # Подпись обязательна: disconnect раньше УДАЛЯЛ запись, и любой желающий
        # мог обнулять счётчик чужими userId. Теперь без валидной подписи — игнор.
        if not signed:
            logger.warning(f"connection/update: rejected unsigned disconnect for userId={user_id}")
            return {"success": 1, "message": "ok"}
        # Мягкое отключение вместо удаления: документ остаётся (история видна),
        # TTL-индекс удалит его сам через TTL_EXPIRE_SECONDS.
        await collection.update_one(
            {"userId": user_id},
            {"$set": {"disconnectedAt": now, "lastSeen": now}},
        )

    elif action == "heartbeat":
        if not signed:
            logger.warning(f"connection/update: unsigned heartbeat from userId={user_id}")
        # КЛЮЧЕВОЙ ФИКС: upsert=True. Раньше heartbeat не воскрешал запись,
        # и юзер, чья запись один раз удалилась чисткой, пропадал из счётчика
        # НАВСЕГДА, продолжая слать heartbeat'ы в пустоту.
        #
        # Фильтр с $or — грейс после disconnect: если юзер только что (90 сек)
        # явно отключился, опоздавший heartbeat не воскрешает его. У живого
        # подключения heartbeat'ы идут каждые 60 сек, так что настоящий онлайн
        # восстановится максимум за 2 такта.
        grace_cutoff = now - timedelta(seconds=DISCONNECT_GRACE_SECONDS)
        try:
            await collection.update_one(
                {
                    "userId": user_id,
                    "$or": [
                        {"disconnectedAt": {"$exists": False}},
                        {"disconnectedAt": {"$lt": grace_cutoff}},
                    ],
                },
                {
                    "$set": {
                        "userId": user_id,
                        "lastSeen": now,
                        "serverIp": server_ip,
                        "protocol": protocol,
                        "signed": signed,
                    },
                    "$setOnInsert": {"connectedAt": now},
                    "$unset": {"disconnectedAt": ""},
                },
                upsert=True,
            )
        except DuplicateKeyError:
            # Документ существует, но не прошёл фильтр => недавний disconnect.
            # Это и есть «опоздавший» heartbeat — молча игнорируем.
            pass

    return {"success": 1, "message": "ok"}


# ── Кэш статистики (бот опрашивает каждые 3 сек) ─────────────────────────────
_stats_cache: dict = {"ts": 0.0, "data": None}
_stats_lock = asyncio.Lock()


@router.get("/vpn/api/v1/bot/servers/stats")
async def get_servers_stats():
    # Лёгкий кэш: при открытой админке бот дёргает эндпоинт каждые 3 сек,
    # незачем каждый раз перечитывать все коллекции.
    now_mono = time_module.monotonic()
    if _stats_cache["data"] is not None and now_mono - _stats_cache["ts"] < STATS_CACHE_SECONDS:
        return _stats_cache["data"]

    async with _stats_lock:
        now_mono = time_module.monotonic()
        if _stats_cache["data"] is not None and now_mono - _stats_cache["ts"] < STATS_CACHE_SECONDS:
            return _stats_cache["data"]

        from src.db.v1.server_pojo import ServerPojo as Ikev2ServerPojo
        from src.db.v3.a3xui.server_pojo import ServerPojo as VlessServerPojo
        from src.db.v3.awg.server_pojo import ServerPojo as AwgServerPojo

        ikev2_servers = await Ikev2ServerPojo.find_all()
        vless_servers = await VlessServerPojo.find_all()
        awg_servers = await AwgServerPojo.find_all()

        collection = await _get_collection()

        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=ONLINE_WINDOW_MINUTES)

        # Раньше тут был delete_many (чистка при КАЖДОМ просмотре статистики —
        # гонка с heartbeat'ами). Теперь чтение ничего не удаляет:
        # окно онлайна — это просто фильтр, физическую чистку делает TTL-индекс.
        active = await collection.find(
            {
                "lastSeen": {"$gte": window_start},
                "disconnectedAt": {"$exists": False},
            }
        ).to_list(length=None)

        total_online = len(active)
        ikev2_online = sum(1 for c in active if _normalize_protocol(c.get("protocol", "")) == "ikev2")
        vless_online = sum(1 for c in active if _normalize_protocol(c.get("protocol", "")) == "vless")
        awg_online = sum(1 for c in active if _normalize_protocol(c.get("protocol", "")) == "awg")

        # Count by server
        server_counts_by_protocol = {
            "ikev2": {},
            "vless": {},
            "awg": {},
        }
        for c in active:
            ip = c.get("serverIp", "")
            if not ip:
                continue
            protocol = _normalize_protocol(c.get("protocol", ""))
            protocol_counts = server_counts_by_protocol[protocol]
            protocol_counts[ip] = protocol_counts.get(ip, 0) + 1

        # Build response
        ikev2_data = []
        for s in ikev2_servers:
            ikev2_data.append({
                "ipAddress": s.ip_address,
                "country": s.country,
                "countryCode": s.country_code,
                "status": s.status,
                "premium": s.premium,
                "onlineUsers": server_counts_by_protocol["ikev2"].get(s.ip_address, 0),
            })

        vless_data = []
        for s in vless_servers:
            # Vless domain or ip usually acts as the serverIp in active connections
            ip = s.server_domain_port_path.split(":")[0] if s.server_domain_port_path else s.server_ip
            vless_data.append({
                "ipAddress": s.server_ip,
                "domain": s.server_domain_port_path,
                "description": s.description,
                "onlineUsers": server_counts_by_protocol["vless"].get(
                    ip,
                    server_counts_by_protocol["vless"].get(s.server_ip, 0),
                ),
            })

        awg_data = []
        for s in awg_servers:
            awg_data.append({
                "ipAddress": s.ip_address,
                "country": s.country,
                "countryCode": s.country_code,
                "status": s.status,
                "premium": s.premium,
                "onlineUsers": server_counts_by_protocol["awg"].get(s.ip_address, 0),
            })

        response = {
            "success": 1,
            "data": {
                "totalServers": len(ikev2_servers) + len(vless_servers) + len(awg_servers),
                "ikev2Servers": len(ikev2_servers),
                "vlessServers": len(vless_servers),
                "awgServers": len(awg_servers),
                "totalOnline": total_online,
                "ikev2Online": ikev2_online,
                "vlessOnline": vless_online,
                "awgOnline": awg_online,
                "onlineWindowMinutes": ONLINE_WINDOW_MINUTES,
                "servers": ikev2_data,
                "vlessServersList": vless_data,
                "awgServersList": awg_data,
            },
        }

        _stats_cache["data"] = response
        _stats_cache["ts"] = time_module.monotonic()
        return response


@router.post("/vpn/api/v1/user/servers/load")
async def get_servers_load():
    """
    Returns server load as percentage to be used by Android clients.
    """
    from src.db.v1.server_pojo import ServerPojo as Ikev2ServerPojo
    from src.db.v3.a3xui.server_pojo import ServerPojo as VlessServerPojo
    from src.db.v3.awg.server_pojo import ServerPojo as AwgServerPojo
    from src.utils.server_metrics import SERVER_METRICS_STATE

    ikev2_servers = await Ikev2ServerPojo.find_all()
    vless_servers = await VlessServerPojo.find_all()
    awg_servers = await AwgServerPojo.find_all()

    load_data = {}

    # Load all tracked metrics (which includes Remnawave VLESS servers and active IKEv2)
    for ip_or_host, data in SERVER_METRICS_STATE.items():
        load_data[ip_or_host] = data.get("load_percent", 1)

    # Ensure DB servers are also included with default 1% if they lack metrics
    for s in ikev2_servers:
        ip = s.ip_address
        if ip and ip not in load_data:
            load_data[ip] = 1

    for s in vless_servers:
        host = s.server_ip if s.server_ip else s.server_domain_port_path_sub.split(":")[0]
        if host and host not in load_data:
            load_data[host] = 1

    for s in awg_servers:
        ip = s.ip_address
        if ip and ip not in load_data:
            load_data[ip] = 1

    logger.debug(f"servers/load: SERVER_METRICS_STATE keys={list(SERVER_METRICS_STATE.keys())}")
    logger.debug(f"servers/load: load_data={load_data}")

    return {
        "success": 1,
        "data": load_data
    }
