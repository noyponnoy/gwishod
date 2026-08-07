import hashlib
import logging
import time as time_module

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

logger = logging.getLogger(__name__)

ALLOWED_BUNDLE_IDS = [
    "app.greywebs.vpn",           # Android
    "com.greywebs.greywebsvpn",    # iOS
]
EXPECTED_SECRET = "strongVPN!@#"
MAX_TIME_DRIFT_SECONDS = 3600  # 1 час


class AndroidSignatureMiddleware(BaseHTTPMiddleware):
    """
    Проверяет подпись клиента (hash/time/bundleId) для POST запросов
    на /vpn/api/v1/user/* маршрутах.

    Клиент отправляет в каждом POST-запросе:
      - hash: SHA-256 от "{unixtime}|strongVPN!@#"
      - time: Unix timestamp в секундах
      - bundleId: "app.greywebs.vpn" (Android) или "com.greywebs.greywebsvpn" (iOS)
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        method = request.method

        # Проверяем только POST на /vpn/api/v1/user/*
        if method != "POST" or not path.startswith("/vpn/api/v1/user/"):
            return await call_next(request)

        # Читаем body (можно прочитать только один раз)
        body_bytes = await request.body()
        body_str = body_bytes.decode("utf-8")

        params: dict[str, str] = {}
        for pair in body_str.split("&"):
            parts = pair.split("=", 1)
            if len(parts) == 2:
                params[parts[0]] = parts[1]

        req_hash = params.get("hash", "").strip()
        req_time = params.get("time", "").strip()
        req_bundle = params.get("bundleId", "").strip()

        # 1. Проверяем наличие обязательных полей
        if not req_hash or not req_time or not req_bundle:
            logger.warning("Auth rejected: missing hash/time/bundleId for %s", path)
            return JSONResponse(
                status_code=403,
                content={"success": 0, "message": "Invalid request signature", "data": {}},
            )

        # 2. Проверяем bundleId
        if req_bundle not in ALLOWED_BUNDLE_IDS:
            logger.warning("Auth rejected: invalid bundleId '%s' for %s", req_bundle, path)
            return JSONResponse(
                status_code=403,
                content={"success": 0, "message": "Invalid request signature", "data": {}},
            )

        # 3. Проверяем время (не старше 5 минут)
        try:
            req_timestamp = int(req_time)
        except ValueError:
            logger.warning("Auth rejected: invalid time value '%s' for %s", req_time, path)
            return JSONResponse(
                status_code=403,
                content={"success": 0, "message": "Invalid request signature", "data": {}},
            )

        current_timestamp = int(time_module.time())
        drift = abs(current_timestamp - req_timestamp)
        if drift > MAX_TIME_DRIFT_SECONDS:
            logger.warning("Auth rejected: time drift %ds for %s", drift, path)
            return JSONResponse(
                status_code=403,
                content={"success": 0, "message": "Invalid request signature", "data": {}},
            )

        # 4. Проверяем hash: SHA-256 от "{time}|strongVPN!@#"
        expected_raw = f"{req_time}|{EXPECTED_SECRET}"
        expected_hash = hashlib.sha256(expected_raw.encode()).hexdigest()

        if req_hash != expected_hash:
            logger.warning("Auth rejected: hash mismatch for %s", path)
            return JSONResponse(
                status_code=403,
                content={"success": 0, "message": "Invalid request signature", "data": {}},
            )

        # Подпись валидна — пропускаем запрос дальше
        return await call_next(request)
