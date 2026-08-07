import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field
from starlette.responses import PlainTextResponse

from src.db.v1.invoice_pojo import InvoicePojo
from src.db.v1.user_pojo import UserPojo
from src.db.v2.tariff_pojo import TariffPojo
from src.db.v3.code.code_pojo import CodePojo
from src.db.v3.payments.invoice_pojo import InvoicePojo as InvoicePojoV3
from src.db.v3.a3xui.invoce_pojo import InvoicePojo as InvoicePojoV3Xui
from src.db.v3.a3xui.tariff_pojo import TariffPojo as TariffPojoV3Xui
from src.db.v3.user.user_pojo import UserPojo as UserPojoV3
from src.client_3xui_api import client as client_3xui
from src.db.v1.invoice_currency import InvoiceCurrency
from src.db.v1.invoice_status import InvoiceStatus

logger = logging.getLogger(__name__)

router = APIRouter()


class WebhookNotification(BaseModel):
    transactionType: str = Field(alias="transactionType")
    transactionId: str = Field(alias="transactionId")
    transactionStatus: str = Field(alias="transactionStatus")
    terminalPublicId: str = Field(alias="terminalPublicId")
    errorCode: Optional[str] = Field(default=None, alias="errorCode")
    errorDescription: Optional[str] = Field(default=None, alias="errorDescription")
    terminalName: str = Field(alias="terminalName")
    amount: float
    currency: str
    orderId: str = Field(alias="orderId")
    orderDescription: str = Field(alias="orderDescription")
    paymentTime: str = Field(alias="paymentTime")
    commission: float
    email: Optional[str] = None

    model_config = {"populate_by_name": True}


@router.post("/vpn/client/payment/webhook")
async def web_hook(request_body: WebhookNotification):
    if request_body.transactionStatus != "Paid":
        logger.error(
            "Payment received<br>Invalid transaction status: %s<br>Transaction ID: %s",
            request_body.transactionStatus, request_body.transactionId,
        )
        return PlainTextResponse("Invalid transaction status", status_code=400)

    transaction = request_body
    out_sum = str(transaction.amount)
    inv_id = transaction.transactionId
    shp_invoiceid = transaction.orderId
    p_email = transaction.email or ""
    p_phone = ""
    commission = str(transaction.commission)

    if shp_invoiceid.startswith("VPNCODE"):
        code = CodePojo()
        code.code = shp_invoiceid.replace("VPNCODE", "")
        try:
            code = await code.find_by_code()
        except Exception as e:
            logger.error(
                "Payment received<br>Error finding code<br>Code: %s<br>Transaction ID: %s<br>Error: %s",
                shp_invoiceid, inv_id, e,
            )
            return PlainTextResponse("Internal Server Error", status_code=500)

        if code is None:
            logger.error("Payment received<br>Code not found<br>Code: %s<br>Transaction ID: %s", shp_invoiceid, inv_id)
            return PlainTextResponse("Code not found", status_code=404)

        code.purchased = int(datetime.now(timezone.utc).timestamp() * 1000)
        try:
            result_upd = await code.update()
        except Exception as e:
            logger.error(
                "Payment received<br>Code not updated<br>User: %s<br>Amount: %s<br>Transaction ID: %s<br>Error: %s",
                code.user_id, out_sum, inv_id, e,
            )
            return PlainTextResponse("Internal Server Error", status_code=500)

        if result_upd:
            logger.debug("Payment received<br>Code updated<br>User: %s<br>Amount: %s<br>Transaction ID: %s",
                         code.user_id, out_sum, inv_id)
            return PlainTextResponse(f"OK{inv_id}", status_code=200)
        else:
            logger.error("Payment received<br>Code not updated<br>User: %s<br>Amount: %s<br>Transaction ID: %s",
                         code.user_id, out_sum, inv_id)
            return PlainTextResponse("Internal Server Error", status_code=500)

    elif shp_invoiceid.startswith("subscription"):
        invoice = InvoicePojoV3()
        invoice.invoice_id = shp_invoiceid
        try:
            invoice = await invoice.find_by_id()
        except Exception as e:
            logger.error(
                "Payment received<br>Error finding invoice<br>Invoice ID: %s<br>Transaction ID: %s<br>Error: %s",
                shp_invoiceid, inv_id, e,
            )
            return PlainTextResponse("Internal Server Error", status_code=500)

        if invoice is None:
            logger.error("Payment received<br>Invoice not found<br>Invoice ID: %s<br>Transaction ID: %s",
                         shp_invoiceid, inv_id)
            return PlainTextResponse("Invoice not found", status_code=404)

        invoice.operation_id = inv_id
        invoice.p_email = p_email
        invoice.p_phone = p_phone
        invoice.commission = commission
        invoice.status = True
        invoice.updated = int(datetime.now(timezone.utc).timestamp() * 1000)

        if await invoice.update():
            user = UserPojoV3()
            user.user_id = invoice.user_id
            try:
                user = await user.find_by_user_id()
            except Exception as e:
                logger.error(
                    "Payment received<br>Error finding user<br>User ID: %s<br>Invoice ID: %s<br>Error: %s",
                    invoice.user_id, invoice.invoice_id, e,
                )
                return PlainTextResponse("Internal Server Error", status_code=500)

            if user is None:
                logger.error("Payment received<br>User not found<br>User ID: %s<br>Invoice ID: %s",
                             invoice.user_id, invoice.invoice_id)
                return PlainTextResponse("User not found", status_code=404)

            tariff = TariffPojo()
            tariff.technical_name = invoice.plan
            try:
                tariff = await tariff.find()
            except Exception as e:
                logger.error(
                    "Payment received<br>Error finding tariff<br>Tariff: %s<br>Invoice ID: %s<br>Error: %s",
                    invoice.plan, invoice.invoice_id, e,
                )
                return PlainTextResponse("Internal Server Error", status_code=500)

            if tariff is None:
                logger.error("Payment received<br>Tariff not found<br>Tariff: %s<br>Invoice ID: %s",
                             invoice.plan, invoice.invoice_id)
                return PlainTextResponse("Tariff not found", status_code=404)

            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            if user.premium_end < now_ms:
                user.premium_end = now_ms + tariff.duration
            else:
                user.premium_end = user.premium_end + tariff.duration
            user.is_premium = True

            if await user.update():
                logger.debug(
                    "Payment received<br>User subscription updated<br>User: %s<br>Plan: %s<br>Amount: %s<br>Invoice ID: %s",
                    user.user_id, tariff.technical_name, out_sum, invoice.invoice_id,
                )
                return PlainTextResponse(f"OK{inv_id}", status_code=200)
            else:
                logger.error(
                    "Payment received<br>User subscription not updated<br>User: %s<br>Plan: %s<br>Amount: %s<br>Invoice ID: %s",
                    user.user_id, tariff.technical_name, out_sum, invoice.invoice_id,
                )
                return PlainTextResponse("Internal Server Error", status_code=500)
        else:
            logger.error("Payment received<br>Invoice not updated<br>User: %s<br>Amount: %s<br>Invoice ID: %s",
                         invoice.user_id, out_sum, invoice.invoice_id)
            return PlainTextResponse("Internal Server Error", status_code=500)

    elif shp_invoiceid.startswith("bot"):
        invoice = InvoicePojoV3Xui()
        invoice.invoice_id = shp_invoiceid
        try:
            invoice = await invoice.find()
        except Exception as e:
            logger.error(
                "Payment received<br>Error finding bot invoice<br>Invoice ID: %s<br>Transaction ID: %s<br>Error: %s",
                shp_invoiceid, inv_id, e,
            )
            return PlainTextResponse("Internal Server Error", status_code=500)

        tariff = TariffPojoV3Xui()
        tariff.name = invoice.tariff_name
        try:
            tariff = await tariff.find()
        except Exception as e:
            logger.error(
                "Payment received<br>Error finding tariff<br>Tariff: %s<br>Invoice ID: %s<br>Error: %s",
                invoice.tariff_name, inv_id, e,
            )
            return PlainTextResponse("Internal Server Error", status_code=500)

        t_name = tariff.t_name
        tg_id = invoice.tg_id

        if not invoice.paid:
            invoice.paid = True
            if await invoice.update():
                try:
                    result = await client_3xui.update_user_payment(tg_id, t_name, None)
                except Exception as e:
                    logger.error(
                        "Payment received<br>Bot subscription not updated<br>User: %s<br>Plan: %s<br>Amount: %s<br>Transaction ID: %s<br>Error: %s",
                        tg_id, t_name, out_sum, inv_id, e,
                    )
                    return PlainTextResponse("Internal Server Error", status_code=500)

                if result:
                    logger.debug(
                        "Payment received<br>Bot subscription updated<br>User: %s<br>Plan: %s<br>Amount: %s<br>Transaction ID: %s",
                        tg_id, t_name, out_sum, inv_id,
                    )
                    tariff_messages = {
                        1: "Платеж {} зачислен.\nТариф Lite активирован на 30 дней",
                        2: "Платеж {} зачислен.\nТариф Pro активирован на 30 дней",
                        3: "Платеж {} зачислен.\nТариф Lite активирован на 90 дней",
                        4: "Платеж {} зачислен.\nТариф Pro активирован на 90 дней",
                    }
                    msg_template = tariff_messages.get(t_name)
                    if msg_template:
                        url = (
                            f"http://localhost:8080/notification?"
                            f"tg_id={quote(str(tg_id))}"
                            f"&message={quote(msg_template.format(inv_id))}"
                            f"&image={quote('null')}"
                            f"&type={quote('ALERT')}"
                            f"&fileType={quote('null')}"
                        )
                        try:
                            async with httpx.AsyncClient() as http_client:
                                await http_client.get(url)
                        except Exception as e:
                            logger.error(
                                "Failed to send notification<br>User: %s<br>Transaction ID: %s<br>Error: %s",
                                tg_id, inv_id, e,
                            )
                    return PlainTextResponse(f"OK{inv_id}", status_code=200)
                else:
                    logger.error(
                        "Payment received<br>Bot subscription not updated<br>User: %s<br>Plan: %s<br>Amount: %s<br>Transaction ID: %s",
                        tg_id, t_name, out_sum, inv_id,
                    )
                    return PlainTextResponse("Internal Server Error", status_code=500)
            else:
                logger.error(
                    "Payment received<br>Bot subscription invoice not updated<br>User: %s<br>Plan: %s<br>Amount: %s<br>Transaction ID: %s",
                    tg_id, t_name, out_sum, inv_id,
                )
                return PlainTextResponse("Internal Server Error", status_code=500)
        else:
            logger.error(
                "Payment received<br>Bot subscription has already been paid<br>User: %s<br>Plan: %s<br>Amount: %s<br>Transaction ID: %s",
                tg_id, t_name, out_sum, inv_id,
            )
            return PlainTextResponse(f"OK{inv_id}", status_code=200)

    else:
        # Default v1 invoice flow
        invoice = InvoicePojo()
        invoice.invoice_id = shp_invoiceid
        try:
            invoice = await invoice.find_by_id()
        except Exception as e:
            logger.error(
                "Payment received<br>Error finding invoice<br>Invoice ID: %s<br>Transaction ID: %s<br>Error: %s",
                shp_invoiceid, inv_id, e,
            )
            return PlainTextResponse("Internal Server Error", status_code=500)

        if invoice is None:
            logger.error("Payment received<br>Invoice not found<br>Invoice ID: %s<br>Transaction ID: %s",
                         shp_invoiceid, inv_id)
            return PlainTextResponse("Invoice not found", status_code=404)

        invoice.fk_operation_id = inv_id
        invoice.p_email = p_email
        invoice.p_phone = p_phone
        invoice.currency = InvoiceCurrency.other
        invoice.payer_account = ""
        invoice.commission = commission
        invoice.status = InvoiceStatus.PAID
        invoice.updated = InvoicePojo.now()

        try:
            result_upd = await invoice.update()
        except Exception as e:
            logger.error(
                "Payment received<br>Invoice not updated<br>User: %s<br>Amount: %s<br>Transaction ID: %s<br>Error: %s",
                invoice.user_id, out_sum, inv_id, e,
            )
            return PlainTextResponse("Internal Server Error", status_code=500)

        if result_upd:
            user_id = invoice.user_id
            user = UserPojo()
            user.device_id = user_id
            try:
                user = await user.find()
            except Exception as e:
                logger.error(
                    "Payment received<br>Error finding user<br>User ID: %s<br>Invoice ID: %s<br>Error: %s",
                    user_id, invoice.invoice_id, e,
                )
                return PlainTextResponse("Internal Server Error", status_code=500)

            if user is None:
                logger.error("Payment received<br>User not found<br>User ID: %s<br>Invoice ID: %s",
                             user_id, invoice.invoice_id)
                return PlainTextResponse("User not found", status_code=404)

            tariff = TariffPojo()
            tariff.technical_name = invoice.plan
            try:
                tariff = await tariff.find()
            except Exception as e:
                logger.error(
                    "Payment received<br>Error finding tariff<br>Tariff: %s<br>Invoice ID: %s<br>Error: %s",
                    invoice.plan, invoice.invoice_id, e,
                )
                return PlainTextResponse("Internal Server Error", status_code=500)

            if tariff is None:
                logger.error("Payment received<br>Tariff not found<br>Tariff: %s<br>Invoice ID: %s",
                             invoice.plan, invoice.invoice_id)
                return PlainTextResponse("Tariff not found", status_code=404)

            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            if user.premium_end_millis() < now_ms:
                user.premium_end = UserPojo.from_millis(now_ms + tariff.duration)
            else:
                user.premium_end = UserPojo.from_millis(user.premium_end_millis() + tariff.duration)
            user.is_premium = True

            try:
                result_upd_user = await user.update()
            except Exception as e:
                logger.error(
                    "Payment received<br>User not updated<br>User: %s<br>Plan: %s<br>Amount: %s<br>Transaction ID: %s<br>Error: %s",
                    user_id, tariff.technical_name, out_sum, inv_id, e,
                )
                return PlainTextResponse("Internal Server Error", status_code=500)

            if result_upd_user:
                logger.debug("Payment received<br>User: %s<br>Plan: %s<br>Sum: %s",
                             user_id, tariff.technical_name, out_sum)
                return PlainTextResponse(f"OK{inv_id}", status_code=200)
            else:
                logger.error("Payment received<br>User not updated<br>User: %s<br>Plan: %s<br>Sum: %s",
                             user_id, tariff.technical_name, out_sum)
                return PlainTextResponse("Internal Server Error", status_code=500)
        else:
            logger.error("Payment received<br>Invoice not updated<br>User: %s<br>Amount: %s<br>Invoice ID: %s",
                         invoice.user_id, out_sum, inv_id)
            return PlainTextResponse("Internal Server Error", status_code=500)
