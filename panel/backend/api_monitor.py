"""Фоновый мониторинг здоровья главного API.

Аналог bot/services/api_monitor.py, но БЕЗ Telegram-уведомлений
(ими занимается бот, чтобы не дублировать). Панель лишь показывает
индикатор статуса на дашборде.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta

import httpx

from .config import API_DOCS_URL

logger = logging.getLogger(__name__)

_state = {
    "is_up": True,
    "latency": 0,
    "status_text": "—",
    "downtime_start": None,
    "initialized": False,
    "last_check": 0,
}
_lock = asyncio.Lock()


def _moscow_time() -> str:
    tz = timezone(timedelta(hours=3))
    return datetime.now(tz).strftime("%H:%M:%S")


def _downtime_str(start: float) -> str:
    if not start:
        return "—"
    diff = int(time.time() - start)
    if diff < 60:
        return f"{diff} сек"
    minutes = diff // 60
    if minutes < 60:
        return f"~{minutes} мин"
    return f"~{minutes // 60} ч {minutes % 60} мин"


async def _check_once() -> tuple[bool, int, str]:
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(API_DOCS_URL)
            latency = int((time.time() - start) * 1000)
            if r.status_code == 200:
                return True, latency, f"{r.status_code} OK"
            return False, latency, f"{r.status_code} {r.reason_phrase}"
    except httpx.TimeoutException:
        return False, int((time.time() - start) * 1000), "timeout"
    except Exception as e:
        return False, int((time.time() - start) * 1000), str(e)[:80]


async def _monitor_loop():
    while True:
        try:
            is_up, latency, status = await _check_once()
            now = time.time()
            async with _lock:
                was_up = _state["is_up"]
                _state["is_up"] = is_up
                _state["latency"] = latency
                _state["status_text"] = status
                _state["last_check"] = now
                _state["initialized"] = True
                if was_up and not is_up:
                    _state["downtime_start"] = now
                elif not was_up and is_up:
                    _state["downtime_start"] = None
        except Exception as e:
            logger.warning("monitor loop error: %s", e)
        await asyncio.sleep(60)


def start_monitor():
    """Запускает фоновую задачу мониторинга (вызывается из app startup)."""
    asyncio.create_task(_monitor_loop())


def get_status() -> dict:
    return {
        "isUp": _state["is_up"],
        "latency": _state["latency"],
        "statusText": _state["status_text"],
        "initialized": _state["initialized"],
        "downtime": _downtime_str(_state["downtime_start"]),
        "lastCheck": _state["last_check"],
        "moscowTime": _moscow_time(),
    }
