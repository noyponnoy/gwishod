import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.db.v1.invoice_pojo import InvoicePojo, InvoiceJson2
from src.db.v1.privileges import Privileges
from src.db.v1.support_user_pojo import SupportUserPojo

logger = logging.getLogger(__name__)

router = APIRouter()


class UpdateInvoiceRequestJson(BaseModel):
    invoiceData: InvoiceJson2
    supportUser: str


@router.post("/vpn/api/v1/support/updateinvoice")
async def update_invoice(body: UpdateInvoiceRequestJson):
    invoice_json = body.invoiceData
    support_user = body.supportUser

    r_user = SupportUserPojo()
    r_user.user = support_user
    r_user = await r_user.find()

    has_permission = (
        (r_user.privileges == Privileges.ADMIN and r_user.enabled_update)
        or (r_user.privileges == Privileges.SUPPORT and r_user.enabled_update)
    )

    if has_permission:
        invoice = InvoicePojo(
            invoice_id=invoice_json.invoice_id,
            user_id=invoice_json.user_id,
            amount=invoice_json.amount,
            currency=invoice_json.currency,
            status=invoice_json.status,
            pay_url=invoice_json.pay_url,
            created=invoice_json.created,
            updated=invoice_json.updated,
            fk_operation_id=invoice_json.fk_operation_id,
            p_email=invoice_json.p_email,
            p_phone=invoice_json.p_phone,
            payer_account=invoice_json.payer_account,
            commission=invoice_json.commission,
            plan=invoice_json.plan,
        )
        result = await invoice.update()

        if result:
            return {"error": False, "message": "invoice updated"}
        else:
            return {"error": True, "message": "invoice not updated"}
    else:
        return JSONResponse(
            status_code=401,
            content={"error": True, "message": "invoice not updated"},
        )
