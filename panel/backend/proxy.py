"""Прокси-слой к существующему API сервера."""
import hashlib
import json
import logging
import time
from typing import Any, Optional
import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from .auth import get_current_user
from .config import API_BASE_URL
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/proxy", tags=["proxy"])
_client = httpx.AsyncClient(timeout=30.0)
JSON_BODY_PATHS = {
    "/vpn/api/v1/bot/servers_awg/create",
    "/vpn/api/v1/bot/servers_awg/delete",
    "/vpn/api/v1/bot/servers_gw/create",
    "/vpn/api/v1/bot/servers_gw/delete",
}
_CACHE = {}
_CACHE_TTL = 5
def _cache_key(method, path, params=None):
    raw = f"{method}:{path}:{json.dumps(params or {}, sort_keys=True)}"
    return hashlib.md5(raw.encode()).hexdigest()
def _get_cached(key):
    entry = _CACHE.get(key)
    if entry and time.time() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None
def _set_cached(key, data):
    _CACHE[key] = (time.time(), data)
    now = time.time()
    stale = [k for k, (ts, _) in _CACHE.items() if now - ts > _CACHE_TTL * 2]
    for k in stale:
        del _CACHE[k]
async def _request(method, path, params=None, body=None):
    if method == "GET":
        key = _cache_key(method, path, params)
        cached = _get_cached(key)
        if cached is not None:
            return cached
    url = f"{API_BASE_URL}{path}"
    try:
        kwargs = {}
        if params:
            clean = {k: v for k, v in params.items() if v is not None and v != ""}
            if clean:
                kwargs["params"] = clean
        if body is not None:
            if path in JSON_BODY_PATHS:
                kwargs["json"] = body
            else:
                kwargs["data"] = body
        resp = await _client.request(method, url, **kwargs)
        if resp.status_code == 429:
            import asyncio
            await asyncio.sleep(2)
            resp = await _client.request(method, url, **kwargs)
        try:
            result = resp.json()
        except Exception:
            return {"success": 0, "message": f"bad response: {resp.text[:300]}"}
        if method == "GET":
            _set_cached(_cache_key(method, path, params), result)
        return result
    except httpx.HTTPError as e:
        logger.warning("proxy error %s %s: %s", method, path, e)
        return {"success": 0, "message": f"network error: {e}"}
    except Exception as e:
        logger.exception("proxy unexpected error %s %s", method, path)
        return {"success": 0, "message": f"unexpected error: {e}"}
@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(request: Request, path: str, _: str = Depends(get_current_user)):
    full_path = f"/vpn/api/v1/bot/{path}"
    if request.method == "GET":
        params = {k: v for k, v in request.query_params.items()}
        result = await _request("GET", full_path, params=params)
        return JSONResponse(result)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    params = payload.get("params")
    body = payload.get("json")
    result = await _request(request.method, full_path, params=params, body=body)
    return JSONResponse(result)
