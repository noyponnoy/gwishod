import logging
import os
import uuid

from fastapi import Request, UploadFile, File
from starlette.responses import JSONResponse, PlainTextResponse

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB — matches Rust RequestBodyLimitLayer


async def upload_file(request: Request, file: UploadFile = File(...)):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_SIZE:
        return PlainTextResponse("Файл слишком большой", status_code=413)

    if not file or not file.filename:
        return PlainTextResponse("Файл не был предоставлен", status_code=400)

    original_name = file.filename.strip("\"'")
    unique_name = f"{uuid.uuid4()}_{original_name}"
    file_path = f"/root/vpn/{unique_name}"

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        logger.error(f"Ошибка записи файла: {e}")
        return PlainTextResponse(str(e), status_code=500)

    return JSONResponse(status_code=200, content={"filePath": file_path})
