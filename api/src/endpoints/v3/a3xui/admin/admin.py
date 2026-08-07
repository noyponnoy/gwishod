import asyncio
import logging
from urllib.parse import quote

from fastapi import Query as QueryParam
from starlette.responses import PlainTextResponse

from src.db.v3.a3xui.user_pojo import UserPojo
from src.db.v3.a3xui.invoce_pojo import InvoicePojo

import httpx
import time

logger = logging.getLogger(__name__)


async def massnotif(
    message: str = QueryParam(...),
    image: str = QueryParam(...),
    fileType: str = QueryParam(...),
    type: str = QueryParam(..., alias="type"),
    ids: str = QueryParam(None),
):
    logger.debug(f"params: message={message}, image={image}, fileType={fileType}, type={type}, ids={ids}")

    async def _send(msg, img, t_type, ft, id_str):
        try:
            async with httpx.AsyncClient() as http_client:
                url = (
                    f"http://localhost:8080/massnotif?"
                    f"tg_id={quote(id_str)}"
                    f"&message={quote(msg)}"
                    f"&image={quote(img)}"
                    f"&type={quote(t_type)}"
                    f"&fileType={quote(ft)}"
                )
                await http_client.get(url)
            logger.info("Mass notification sent")
        except Exception as e:
            logger.error(str(e))

    actual_ids = ids
    if not actual_ids:
        users = await UserPojo.find_all()
        actual_ids = ";".join(u.tg_id for u in users) + ";"

    asyncio.create_task(_send(message, image, type, fileType, actual_ids))
    return PlainTextResponse("OK", status_code=200)


async def statistics(
    startDate: int = QueryParam(..., alias="startDate"),
    endDate: int = QueryParam(..., alias="endDate"),
):
    invoices = await InvoicePojo.find_all()
    users = await UserPojo.find_all()

    filtered_invoices = []
    filtered_users = []
    active_users = []
    active_paid_users = []

    for invoice in invoices:
        if hasattr(invoice, '_id') and invoice._id:
            try:
                oid_bytes = invoice._id.binary if hasattr(invoice._id, 'binary') else bytes.fromhex(str(invoice._id))
                invoice_date = int.from_bytes(oid_bytes[0:4], byteorder='big')
            except Exception:
                continue
        else:
            continue
        if startDate <= invoice_date <= endDate:
            filtered_invoices.append(invoice)

    for user in users:
        if hasattr(user, '_id') and user._id:
            try:
                oid_bytes = user._id.binary if hasattr(user._id, 'binary') else bytes.fromhex(str(user._id))
                user_date = int.from_bytes(oid_bytes[0:4], byteorder='big')
            except Exception:
                continue
        else:
            continue
        if startDate <= user_date <= endDate:
            filtered_users.append(user)

    now_ms = int(time.time() * 1000)
    for user in users:
        expired_at = getattr(user, 'expired_at', {})
        if isinstance(expired_at, dict):
            exp1 = expired_at.get("1", 0)
            exp2 = expired_at.get("2", 0)
            if exp1 >= now_ms or exp2 >= now_ms:
                active_users.append(user)

    seen_users = set()
    now_sec = int(time.time())
    for invoice in invoices:
        if not invoice.paid:
            continue
        matching_user = None
        for u in active_users:
            if u.tg_id == invoice.tg_id:
                matching_user = u
                break
        if matching_user:
            try:
                if hasattr(invoice, '_id') and invoice._id:
                    oid_bytes = invoice._id.binary if hasattr(invoice._id, 'binary') else bytes.fromhex(str(invoice._id))
                    invoice_date = int.from_bytes(oid_bytes[0:4], byteorder='big')
                else:
                    continue
            except Exception:
                continue
            if invoice_date + 2592000 >= now_sec and matching_user.tg_id not in seen_users:
                seen_users.add(matching_user.tg_id)
                active_paid_users.append(matching_user)

    period_sum = 0.0
    for inv in invoices:
        if not inv.paid:
            continue
        try:
            if hasattr(inv, '_id') and inv._id:
                oid_bytes = inv._id.binary if hasattr(inv._id, 'binary') else bytes.fromhex(str(inv._id))
                inv_date = int.from_bytes(oid_bytes[0:4], byteorder='big')
            else:
                continue
        except Exception:
            continue
        if startDate <= inv_date <= endDate:
            try:
                period_sum += float(inv.invoice_amount)
            except (ValueError, TypeError):
                pass

    all_sum = 0.0
    for inv in invoices:
        if not inv.paid:
            continue
        try:
            all_sum += float(inv.invoice_amount)
        except (ValueError, TypeError):
            pass

    result = ""
    result += f"Новых юзеров за выбранный период: {len(filtered_users)};\n"
    result += f"Новых счетов за выбранный период: {len(filtered_invoices)};\n"
    result += f"Активных юзеров на данный момент: {len(active_users)};\n"
    result += f"Активных юзеров на тестовой подписке: {len(active_users) - len(active_paid_users)};\n"
    result += f"Всего покупок за выбранный период: {period_sum} руб.;\n"
    result += f"Всего покупок за все время: {all_sum} руб.;\n"

    return PlainTextResponse(result, status_code=200)
