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


async def fetch_and_update_metric(client: httpx.AsyncClient, ip: str):
    try:
        url = f"http://{ip}:9100/metrics"
        resp = await client.get(url, timeout=4.0)
        resp.raise_for_status()
        
        new_tx, new_rx = parse_metrics(resp.text)
        now = time.time()
        
        load_pct = 1 # default min load
        
        if ip in SERVER_METRICS_STATE:
            old = SERVER_METRICS_STATE[ip]
            dt = now - old["timestamp"]
            if 0 < dt < MAX_METRIC_AGE_SECONDS:
                tx_rate = (new_tx - old["tx_bytes"]) / dt
                rx_rate = (new_rx - old["rx_bytes"]) / dt
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
                
        SERVER_METRICS_STATE[ip] = {
            "timestamp": now,
            "tx_bytes": new_tx,
            "rx_bytes": new_rx,
            "load_percent": load_pct
        }
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
