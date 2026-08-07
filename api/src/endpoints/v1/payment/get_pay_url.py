import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from src.db.v1.invoice_pojo import InvoicePojo
from src.db.v2.tariff_pojo import TariffPojo
from src.db.v3.code.code_pojo import CodePojo
from src.db.v3.payments.invoice_pojo import InvoicePojo as InvoicePojoV3
from src.db.v3.a3xui.invoce_pojo import InvoicePojo as InvoicePojoV3Xui
from src.endpoints.response_object import ResponseJson, ResponseJsonMessage

logger = logging.getLogger(__name__)

router = APIRouter()

PAYMENT_API_BASE = "https://api.wata.pro/api/h2h"
PAYMENT_ACCESS_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJQdWJsaWNJZCI6IjNhMWM0MTk2LTk0Y2MtNGYxNS0xNDY4LWI0Mzc2MGE0NjViYiIs"
    "IlRva2VuVmVyc2lvbiI6IjMiLCJleHAiOjE4MDY0MjEzMTksImlzcyI6Imh0dHBzOi8v"
    "YXBpLndhdGEucHJvIiwiYXVkIjoiaHR0cHM6Ly9hcGkud2F0YS5wcm8vYXBpL2gyaCJ9."
    "RlC9w749wNR1Jfq8Ok-CzwXp7ThQHQ9LVoEP7xqhJPg"
)


class PaymentLinkRequest(BaseModel):
    amount: float
    currency: str
    description: str
    orderId: str
    successRedirectUrl: str
    failRedirectUrl: str
    expirationDateTime: str


async def create_payment_link(request: PaymentLinkRequest) -> dict:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {PAYMENT_ACCESS_TOKEN}",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{PAYMENT_API_BASE}/links",
            headers=headers,
            json=request.model_dump(),
        )
    if response.is_success:
        return response.json()
    raise Exception(f"API error: {response.text}")


def _error_response(status_code: int, info: str):
    return JSONResponse(
        status_code=status_code,
        content=ResponseJson(
            success=False,
            message=ResponseJsonMessage(status_code=status_code, info=info),
            data={},
        ).model_dump(),
    )


async def _database_add(
    user_id: str, amount: str, currency: str, invoice_id: str, pay_url: str, plan: str,
) -> bool:
    invoice = InvoicePojo()
    invoice.invoice_id = invoice_id
    invoice.user_id = user_id
    invoice.amount = amount
    invoice.currency = "other"
    invoice.status = "CREATED"
    invoice.pay_url = pay_url
    invoice.created = InvoicePojo.now()
    invoice.updated = InvoicePojo.now()
    invoice.fk_operation_id = ""
    invoice.p_email = ""
    invoice.p_phone = ""
    invoice.payer_account = ""
    invoice.commission = ""
    invoice.plan = plan
    return await invoice.insert()


async def _database_add_v3(
    user_id: str, amount: str, invoice_id: str, pay_url: str, plan: str,
) -> bool:
    invoice = InvoicePojoV3()
    invoice.invoice_id = invoice_id
    invoice.user_id = user_id
    invoice.amount = amount
    invoice.status = False
    invoice.pay_url = pay_url
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    invoice.created = now_ms
    invoice.updated = now_ms
    invoice.p_email = ""
    invoice.p_phone = ""
    invoice.commission = ""
    invoice.plan = plan
    return await invoice.insert()


async def _database_add_3xui_v3(
    user_id: str, amount: str, invoice_id: str, plan: str,
) -> bool:
    invoice = InvoicePojoV3Xui()
    invoice.invoice_id = invoice_id
    invoice.invoice_amount = amount
    invoice.tg_id = user_id
    invoice.tariff_name = plan
    return await invoice.insert()


@router.get("/vpn/api/v1/getpayurl")
@router.post("/vpn/api/v1/getpayurl")
@router.post("/vpn/api/v3/client/payments/getpayurl")
async def get_pay_url(
    system: str = Query(...),
    userId: str = Query(...),
    plan: str = Query(...),
):
    currency = "RUB"
    success_redirect_url = "https://t.me/gwvpn_bot"
    fail_redirect_url = "https://t.me/gwvpn_bot"
    expiration = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()

    if system.lower() == "fk2":
        user_id = userId
        if user_id.startswith("00") and len(user_id) > 128:
            user_id = user_id[2:]

        plan_name = plan
        invoice_id = str(uuid.uuid4())
        user_id = user_id.replace("\r", "").replace("\n", "").strip()

        tariff = TariffPojo()
        tariff.technical_name = plan_name
        try:
            tariff = await tariff.find()
        except Exception as e:
            logger.error(
                "Get Pay URL fk2<br>Error finding tariff<br>User: %s<br>Plan: %s<br>Error: %s",
                user_id, plan_name, e,
            )
            return _error_response(500, "Internal server error")

        if tariff is None:
            logger.error("Get Pay URL fk2<br>Tariff not found<br>User: %s<br>Plan: %s", user_id, plan_name)
            return _error_response(404, "Tariff not found")

        out_sum = tariff.price
        description = f"Оплата тарифа: {tariff.description}"

        request = PaymentLinkRequest(
            amount=out_sum,
            currency=currency,
            description=description,
            orderId=invoice_id,
            successRedirectUrl=success_redirect_url,
            failRedirectUrl=fail_redirect_url,
            expirationDateTime=expiration,
        )

        try:
            resp = await create_payment_link(request)
        except Exception as e:
            logger.error(
                "Get Pay URL fk2<br>Failed to create SBP payment link<br>User: %s<br>Plan: %s<br>Amount: %s<br>Invoice ID: %s<br>Error: %s",
                user_id, plan_name, out_sum, invoice_id, e,
            )
            return _error_response(500, "Failed to create SBP payment link")

        pay_url = resp["url"]
        in_db = await _database_add(user_id, str(out_sum), currency, invoice_id, pay_url, plan_name)
        if in_db:
            logger.debug(
                "Get Pay URL fk2<br>User: %s<br>Plan: %s<br>Amount: %s<br>Invoice ID: %s<br>Pay URL: %s",
                user_id, plan_name, out_sum, invoice_id, pay_url,
            )
            return PlainTextResponse(pay_url, status_code=200)
        else:
            logger.error(
                "Get Pay URL fk2<br>Invoice not inserted in DB<br>User: %s<br>Plan: %s<br>Amount: %s<br>Invoice ID: %s",
                user_id, plan_name, out_sum, invoice_id,
            )
            return _error_response(500, "Invoice not created")

    elif system.lower() == "code":
        code = CodePojo()
        code.user_id = userId
        code.created = int(datetime.now(timezone.utc).timestamp() * 1000)
        code.duration = int(plan)
        raw = (
            str(code.created).encode()
            + str(code.duration).encode()
            + b"dfskljghILHGLIfghAWLIUgflksdhfglWEI&*TY"
        )
        code.code = hashlib.sha256(raw).hexdigest()

        if await code.insert():
            out_sum = 0.0
            description = "Оплата кода: VPN CODE"
            duration_sec = code.duration / 1000

            if duration_sec <= 2_592_000:
                out_sum = 0.000115354938 * duration_sec
            elif duration_sec <= 7_776_000:
                out_sum = 0.000106095679 * duration_sec
            elif duration_sec >= 15_552_000:
                out_sum = 0.000103780864 * duration_sec

            request = PaymentLinkRequest(
                amount=out_sum,
                currency=currency,
                description=description,
                orderId=f"VPNCODE{code.code}",
                successRedirectUrl=success_redirect_url,
                failRedirectUrl=fail_redirect_url,
                expirationDateTime=expiration,
            )

            try:
                resp = await create_payment_link(request)
            except Exception as e:
                logger.error(
                    "Get Pay URL code<br>Failed to create SBP payment link<br>User: %s<br>Error: %s",
                    userId, e,
                )
                return _error_response(500, "Failed to create SBP payment link")

            code.pay_url = resp["url"]
            if await code.update():
                logger.debug(
                    "Get Pay URL code<br>User: %s<br>Amount: %s<br>Pay URL: %s",
                    userId, out_sum, resp["url"],
                )
                return ResponseJson(
                    success=True,
                    message=ResponseJsonMessage(status_code=200, info="SBP payment link generated"),
                    data=resp["url"],
                ).model_dump()
            else:
                logger.error("Get Pay URL code<br>Code not updated in DB<br>User: %s", userId)
                return _error_response(500, "Invoice not created")
        else:
            logger.error("Get Pay URL code<br>Code not inserted to DB<br>User: %s", userId)
            return _error_response(500, "Invoice not created")

    elif system.lower() == "subscription":
        plan_name = plan
        invoice_id = str(uuid.uuid4())
        user_id = userId

        tariff = TariffPojo()
        tariff.technical_name = plan_name
        try:
            tariff = await tariff.find()
        except Exception as e:
            logger.error(
                "Get Pay URL subscription<br>Error finding tariff<br>User: %s<br>Plan: %s<br>Error: %s",
                user_id, plan_name, e,
            )
            return _error_response(500, "Internal server error")

        if tariff is None:
            logger.error("Get Pay URL subscription<br>Tariff not found<br>User: %s<br>Plan: %s", user_id, plan_name)
            return _error_response(404, "Tariff not found")

        out_sum = tariff.price
        description = f"Оплата тарифа: {tariff.description}"

        request = PaymentLinkRequest(
            amount=out_sum,
            currency=currency,
            description=description,
            orderId=f"subscription{invoice_id}",
            successRedirectUrl=success_redirect_url,
            failRedirectUrl=fail_redirect_url,
            expirationDateTime=expiration,
        )

        try:
            resp = await create_payment_link(request)
        except Exception as e:
            logger.error(
                "Get Pay URL subscription<br>Failed to create SBP payment link<br>User: %s<br>Error: %s",
                user_id, e,
            )
            return _error_response(500, "Failed to create SBP payment link")

        pay_url = resp["url"]
        in_db = await _database_add_v3(user_id, str(out_sum), f"subscription{invoice_id}", pay_url, plan_name)
        if in_db:
            logger.debug(
                "Get Pay URL subscription<br>User: %s<br>Plan: %s<br>Amount: %s<br>Invoice ID: %s<br>Pay URL: %s",
                user_id, plan_name, out_sum, invoice_id, pay_url,
            )
            return ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="SBP payment link generated"),
                data=pay_url,
            ).model_dump()
        else:
            logger.error(
                "Get Pay URL subscription<br>Invoice not inserted in DB<br>User: %s<br>Plan: %s",
                user_id, plan_name,
            )
            return _error_response(500, "Invoice not created")

    elif system.lower() == "bot":
        plan_name = plan
        user_id = userId
        invoice_id = str(uuid.uuid4())
        out_sum = 0.0
        description = "Оплата по СБП: VPN-BOT"

        plan_prices = {
            "vip-1": 100.0,
            "vip-2": 300.0,
            "vip-1-3": 300.0,
            "vip-2-3": 900.0,
        }
        out_sum = plan_prices.get(plan_name.lower(), 0.0)

        request = PaymentLinkRequest(
            amount=out_sum,
            currency=currency,
            description=description,
            orderId=f"bot{invoice_id}",
            successRedirectUrl=success_redirect_url,
            failRedirectUrl=fail_redirect_url,
            expirationDateTime=expiration,
        )

        try:
            resp = await create_payment_link(request)
        except Exception as e:
            logger.error(
                "Get Pay URL bot<br>Failed to create SBP payment link<br>User: %s<br>Error: %s",
                user_id, e,
            )
            return _error_response(500, "Failed to create SBP payment link")

        in_db = await _database_add_3xui_v3(user_id, str(out_sum), f"bot{invoice_id}", plan_name)
        if in_db:
            logger.debug(
                "Get Pay URL bot<br>User: %s<br>Plan: %s<br>Amount: %s<br>Invoice ID: %s<br>Pay URL: %s",
                user_id, plan_name, out_sum, invoice_id, resp["url"],
            )
            return ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="SBP payment link generated"),
                data=resp["url"],
            ).model_dump()
        else:
            logger.error(
                "Get Pay URL bot<br>Invoice not inserted in DB<br>User: %s<br>Plan: %s",
                user_id, plan_name,
            )
            return _error_response(500, "Invoice not created")

    else:
        logger.error("Get Pay URL<br>Bad request<br>User: %s<br>Plan: %s", userId, plan)
        return _error_response(400, "Bad request")
