import asyncio
import json
import logging
import httpx
import time
import re
import os

logger = logging.getLogger(__name__)

# state: ip -> {"timestamp": float, "tx_bytes": float, "rx_bytes": float, "load_percent": int}
SERVER_METRICS_STATE = {}

# 1 Gbps = 1,000,000,000 bits per second = 125,000,000 bytes per second
MAX_BYTES_PER_SEC = 125_000_000.0

# Max time drift to use old data (300 seconds)
MAX_METRIC_AGE_SECONDS = 300

STATE_FILE = os.path.join(os.path.dirname(__file__), "metrics_state.json")

tx_pattern = re.compile(r'node_network_transmit_bytes_total\{[^}]*device="([^"]+)"[^}]*\}\s+([0-9\.eE\+\-]+)')
rx_pattern = re.compile(r'node_network_receive_bytes_total\{[^}]*device="([^"]+)"[^}]*\}\s+([0-9\.eE\+\-]+)')

# ── IKEv2 онлайн напрямую с серверов ─────────────────────────────────────────
# Каждый IKEv2 VPS (strongSwan) отдаёт через node_exporter (textfile-коллектор):
#   ipsec_clients    (gauge) — число UP IKEv2 SA = подключённые клиенты;
#   ipsec_connecting (gauge) — клиенты в процессе подключения.
# Это единственный источник правды для онлайна IKEv2 (heartbeat из приложения
# для IKEv2 больше не используется). VLESS/AWG это не касается.
ipsec_clients_pattern = re.compile(r'^ipsec_clients(?:\{[^}]*\})?\s+([0-9]+(?:\.[0-9]+)?)\s*$', re.MULTILINE)
ipsec_connecting_pattern = re.compile(r'^ipsec_connecting(?:\{[^}]*\})?\s+([0-9]+(?:\.[0-9]+)?)\s*$', re.MULTILINE)

# Онлайн IKEv2 опрашивается отдельным быстрым циклом (update_ipsec_online_loop)
# каждые IPSEC_POLL_INTERVAL_SECONDS секунд — независимо от медленного цикла
# load%/Remnawave (раз в 60 сек).
IPSEC_POLL_INTERVAL_SECONDS = 5
# Как часто перечитывать список IKEv2-серверов из Mongo в быстром цикле.
IPSEC_SERVERS_REFRESH_SECONDS = 30
# Сколько секунд данные ipsec_* считаются свежими.
# При опросе раз в 5 сек 60 сек = терпим до 12 пропущенных опросов
# (транзиентные сетевые сбои), после этого сервер показывает 0 и ⚠️.
IPSEC_STATS_MAX_AGE_SECONDS = 60


def load_state():
    global SERVER_METRICS_STATE
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                SERVER_METRICS_STATE = json.load(f)
            logger.info(f"Loaded metrics state from {STATE_FILE}, {len(SERVER_METRICS_STATE)} entries")
            
            now = time.time()
            expired = []
            for ip, data in SERVER_METRICS_STATE.items():
                if now - data.get("timestamp", 0) > MAX_METRIC_AGE_SECONDS:
                    expired.append(ip)
            for ip in expired:
                del SERVER_METRICS_STATE[ip]
            if expired:
                logger.info(f"Removed {len(expired)} expired entries from metrics state")
    except Exception as e:
        logger.warning(f"Failed to load metrics state: {e}")
        SERVER_METRICS_STATE = {}


def save_state():
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(SERVER_METRICS_STATE, f)
    except Exception as e:
        logger.warning(f"Failed to save metrics state: {e}")


def parse_metrics(text: str):
    tx_total = 0.0
    rx_total = 0.0
    
    for match in tx_pattern.finditer(text):
        dev, val = match.groups()
        if dev not in ("lo", "wg0", "tailscale0"):
            try:
                tx_total += float(val)
            except ValueError:
                pass
                
    for match in rx_pattern.finditer(text):
        dev, val = match.groups()
        if dev not in ("lo", "wg0", "tailscale0"):
            try:
                rx_total += float(val)
            except ValueError:
                pass
                
    return tx_total, rx_total


def parse_ipsec_stats(text: str):
    """Достаёт ipsec_clients / ipsec_connecting из ответа node_exporter.

    Возвращает (clients, connecting). Если метрики ipsec_clients в ответе нет
    (например, это не IKEv2-сервер) — возвращает (None, None).
    """
    clients = None
    connecting = None
    m = ipsec_clients_pattern.search(text)
    if m:
        try:
            clients = int(float(m.group(1)))
        except ValueError:
            clients = None
    m = ipsec_connecting_pattern.search(text)
    if m:
        try:
            connecting = int(float(m.group(1)))
        except ValueError:
            connecting = None
    return clients, connecting


def get_ipsec_stats(ip: str):
    """Свежие данные об онлайне IKEv2-сервера из последнего опроса метрик.

    Возвращает {"clients": int, "connecting": int, "age_seconds": int}
    или None, если данных нет / они устарели (сервер недоступен).
    """
    data = SERVER_METRICS_STATE.get(ip)
    if not data:
        return None
    updated_at = data.get("ipsec_updated_at")
    if not updated_at:
        return None
    age = time.time() - updated_at
    if age > IPSEC_STATS_MAX_AGE_SECONDS:
        return None
    return {
        "clients": int(data.get("ipsec_clients") or 0),
        "connecting": int(data.get("ipsec_connecting") or 0),
        "age_seconds": int(age),
    }


async def fetch_and_update_metric(client: httpx.AsyncClient, ip: str):
    try:
        url = f"http://{ip}:9100/metrics"
        resp = await client.get(url, timeout=4.0)
        resp.raise_for_status()

        new_tx, new_rx = parse_metrics(resp.text)
        ipsec_clients, ipsec_connecting = parse_ipsec_stats(resp.text)
        now = time.time()
        
        load_pct = 1 # default min load
        
        if ip in SERVER_METRICS_STATE:
            old = SERVER_METRICS_STATE[ip]
            # .get: запись могла быть создана быстрым ipsec-циклом,
            # у неё ещё нет timestamp/tx_bytes/rx_bytes.
            dt = now - old.get("timestamp", 0)
            if 0 < dt < MAX_METRIC_AGE_SECONDS:
                tx_rate = (new_tx - old.get("tx_bytes", 0.0)) / dt
                rx_rate = (new_rx - old.get("rx_bytes", 0.0)) / dt
                max_rate = max(tx_rate, rx_rate)
                
                # Calculate percentage against 1Gbps max
                raw_pct = int((max_rate / MAX_BYTES_PER_SEC) * 100)
                raw_pct = min(100, max(1, raw_pct))
                
                # EWMA (Скользящая средняя) для плавности
                old_load = old.get("load_percent", 1)
                load_pct = int(0.4 * raw_pct + 0.6 * old_load)
                load_pct = max(1, min(100, load_pct))
            else:
                load_pct = old.get("load_percent", 1)
                
        entry = {
            "timestamp": now,
            "tx_bytes": new_tx,
            "rx_bytes": new_rx,
            "load_percent": load_pct
        }

        # Онлайн IKEv2: пишем только если метрика реально пришла в этом опросе.
        # Если сервер отвечает, но ipsec_* отсутствует (не IKEv2-хост) — переносим
        # старые значения как есть: их свежесть контролирует ipsec_updated_at.
        if ipsec_clients is not None:
            entry["ipsec_clients"] = ipsec_clients
            entry["ipsec_connecting"] = ipsec_connecting if ipsec_connecting is not None else 0
            entry["ipsec_updated_at"] = now
        elif ip in SERVER_METRICS_STATE:
            old = SERVER_METRICS_STATE[ip]
            for key in ("ipsec_clients", "ipsec_connecting", "ipsec_updated_at"):
                if key in old:
                    entry[key] = old[key]

        SERVER_METRICS_STATE[ip] = entry
        if ipsec_clients is not None:
            logger.info(f"IKEv2 metric OK: {ip} -> load={load_pct}%, ipsec_clients={ipsec_clients}, ipsec_connecting={entry['ipsec_connecting']}")
        else:
            logger.info(f"IKEv2 metric OK: {ip} -> load={load_pct}%")
        
    except httpx.RequestError as e:
        logger.warning(f"IKEv2 metric FAILED: {ip} -> {e}")
    except Exception as e:
        logger.warning(f"IKEv2 metric FAILED: {ip} -> {e}")


async def fetch_remnawave_metrics(client: httpx.AsyncClient):
    try:
        url = "https://panel.gw-vpn.click/api/nodes"
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1dWlkIjoiZWNhZjAzNjQtMDIyZi00ZDY3LTljMzEtZjI4MWFkMGMxZGMyIiwidXNlcm5hbWUiOm51bGwsInJvbGUiOiJBUEkiLCJpYXQiOjE3NzM4NTg1MDcsImV4cCI6MTA0MTM3NzIxMDd9.VB_EbzIvTSemNVuR8VHkByHwARllUQPYSeY22IVtz5U"
        headers = {"Authorization": f"Bearer {token}"}
        
        resp = await client.get(url, headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        
        now = time.time()
        for node in data.get("response", []):
            address = node.get("address")
            if not address:
                continue
                
            total_bytes = float(node.get("trafficUsedBytes", 0))
            load_pct = 1
            
            if address in SERVER_METRICS_STATE:
                old = SERVER_METRICS_STATE[address]
                dt = now - old["timestamp"]
                if 0 < dt < MAX_METRIC_AGE_SECONDS:
                    rate = (total_bytes - old["tx_bytes"]) / dt
                    # rate is in bytes/sec. We compare against 1 Gbps (125 MB/s)
                    raw_pct = int((rate / MAX_BYTES_PER_SEC) * 100)
                    raw_pct = min(100, max(1, raw_pct))
                    
                    # EWMA (Скользящая средняя) для плавности
                    old_load = old.get("load_percent", 1)
                    load_pct = int(0.4 * raw_pct + 0.6 * old_load)
                    load_pct = max(1, min(100, load_pct))
                else:
                    load_pct = old.get("load_percent", 1)
            
            SERVER_METRICS_STATE[address] = {
                "timestamp": now,
                "tx_bytes": total_bytes,
                "rx_bytes": 0.0,
                "load_percent": load_pct
            }
            logger.info(f"Remnawave metric OK: {address} -> load={load_pct}%, trafficUsedBytes={total_bytes}")
            
    except httpx.RequestError as e:
        logger.warning(f"Network error fetching Remnawave metrics: {e}")
    except Exception as e:
        logger.error(f"Error fetching Remnawave metrics: {e}")


async def fetch_ipsec_online(client: httpx.AsyncClient, ip: str):
    """Быстрый опрос ТОЛЬКО онлайна IKEv2 (ipsec_clients / ipsec_connecting).

    Не трогает timestamp/tx_bytes/rx_bytes/load_percent — расчёт load%
    остаётся за медленным циклом update_server_metrics_loop.
    """
    try:
        url = f"http://{ip}:9100/metrics"
        resp = await client.get(url, timeout=4.0)
        resp.raise_for_status()
        clients, connecting = parse_ipsec_stats(resp.text)
        if clients is None:
            # Метрики ipsec_* на сервере нет — свежесть не продлеваем,
            # чтобы стухшие данные честно показались как недоступные.
            return
        entry = SERVER_METRICS_STATE.setdefault(ip, {})
        entry["ipsec_clients"] = clients
        entry["ipsec_connecting"] = connecting if connecting is not None else 0
        entry["ipsec_updated_at"] = time.time()
    except Exception as e:
        # debug, не warning: при опросе раз в 5 сек транзиентные сбои — норма,
        # иначе лог зальёт. Недоступность сервера видно по ⚠️ в боте.
        logger.debug(f"IKEv2 online poll FAILED: {ip} -> {e}")


async def update_ipsec_online_loop():
    """Быстрый цикл онлайна IKEv2: раз в IPSEC_POLL_INTERVAL_SECONDS секунд
    параллельно опрашивает node_exporter всех IKEv2-серверов.

    Отделён от update_server_metrics_loop (60 сек), чтобы не дёргать
    Remnawave и расчёт load% каждые 5 секунд.
    """
    from src.db.v1.server_pojo import ServerPojo as Ikev2ServerPojo

    logger.info(f"Starting fast IKEv2 online poller (every {IPSEC_POLL_INTERVAL_SECONDS} sec)...")
    ips: list = []
    refresh_at = 0.0
    async with httpx.AsyncClient(verify=False) as client:
        while True:
            try:
                # Список серверов перечитываем из Mongo раз в 30 сек,
                # а не на каждый тик.
                now_mono = time.monotonic()
                if now_mono >= refresh_at:
                    servers = await Ikev2ServerPojo.find_all()
                    ips = [s.ip_address for s in servers if s.ip_address]
                    refresh_at = now_mono + IPSEC_SERVERS_REFRESH_SECONDS
                if ips:
                    await asyncio.gather(
                        *[fetch_ipsec_online(client, ip) for ip in ips],
                        return_exceptions=True,
                    )
            except Exception as e:
                logger.error(f"Error in update_ipsec_online_loop: {e}")
            await asyncio.sleep(IPSEC_POLL_INTERVAL_SECONDS)


async def update_server_metrics_loop():
    from src.db.v1.server_pojo import ServerPojo as Ikev2ServerPojo
    from src.db.v3.a3xui.server_pojo import ServerPojo as VlessServerPojo
    
    load_state()
    logger.info("Starting Prometheus metrics collector loop...")
    while True:
        try:
            ikev2_servers = await Ikev2ServerPojo.find_all()
            vless_servers = await VlessServerPojo.find_all()
            
            logger.info(f"Metrics loop: ikev2_servers={len(ikev2_servers)}, vless_servers={len(vless_servers)}")
            
            ips_to_check = set()
            for s in ikev2_servers:
                if s.ip_address:
                    ips_to_check.add(s.ip_address)
            for s in vless_servers:
                if s.server_ip:
                    ips_to_check.add(s.server_ip)

            logger.info(f"Metrics loop: ips_to_check={ips_to_check}")

            async with httpx.AsyncClient(verify=False) as client:
                tasks = []
                if ips_to_check:
                    tasks.extend([fetch_and_update_metric(client, ip) for ip in ips_to_check])
                tasks.append(fetch_remnawave_metrics(client))
                await asyncio.gather(*tasks, return_exceptions=True)
                    
            logger.info(f"Metrics loop: SERVER_METRICS_STATE keys={list(SERVER_METRICS_STATE.keys())}")
            save_state()
                    
        except Exception as e:
            logger.error(f"Error in update_server_metrics_loop: {e}")
            
        await asyncio.sleep(60) # Refresh every 60 seconds
