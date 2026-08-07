"""Дополнительные эндпоинты панели, не входящие в сквозной прокси.

QR-декодинг делаем здесь (нужна криптография, недоступная в браузере),
а поиск пользователя по расшифрованному QR — через стандартный прокси.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .auth import get_current_user
from .qr_decoder import decode_qr_text

router = APIRouter(prefix="/api", tags=["extras"], dependencies=[Depends(get_current_user)])


class QrRequest(BaseModel):
    text: str


@router.post("/qr/decode")
async def qr_decode(req: QrRequest):
    """Принимает сырой QR-текст, возвращает расшифрованный deviceId (или исходный)."""
    device_id = decode_qr_text(req.text)
    if not device_id:
        return JSONResponse({"success": 0, "message": "не удалось распознать QR"})
    return JSONResponse({"success": 1, "deviceId": device_id})
