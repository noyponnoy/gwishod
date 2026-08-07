import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.db.v1.invoice_pojo import InvoicePojo, InvoiceJson
from src.db.v1.privileges import Privileges
from src.db.v1.support_user_pojo import SupportUserPojo
from src.db.v1.user_pojo import UserPojo, UserJson
from src.utils.crypto import Crypto

logger = logging.getLogger(__name__)

router = APIRouter()

PRIVATE_KEY_STR = "30820276020100300D06092A864886F70D0101010500048202603082025C020100028181008C35F91AB0A69B721771F0E384A9496D336D5732F4392F1A1E5706916CC7814FDCE7A3F4521428D503B55CCE57FDB6F8E324E6ED25E5C2D179331F06DAC1810E716301BEEF99A8F1D0BFDA7C1A2C11AF979E8CAE86DC1680516F353E5642E35B01160B5C3A48E56E225201F64E44F4DF1EEB1D4CB80D438D4820291E448308BD0203010001028180726617398FA8606C5674C0F6E1E6BDE23B739B1217F2105C5F24E257054A4257C705B8E03F97F338DA2DBFEB1C20068A4BCA70204E2B8929209A755642665FC5124E0FF5F5F7C05D06491D9F33C8405DA494784826A9B4F1AD69E7085E9CF7110F4AF36D01C955ACDFF0C75397A9024ED18C5A767ACE4863FD80D6A2B1549001024100D13E84444FD264B2238E2B875294373D7EEB4AFEC6E7FE8273160ACCDE5C150EAF6E4765EC2795EB793840D5C936F4BFAA8E1835C0B4E294D26E5A5F494B541D024100AB8A82F99995ACF0707F2F4CA254591D81674898C64D6E6B657E4BC0F3F82AC3C92BF72B84901DC447D42A82446B7B7D45A8F34E045835D5592D09DD6E29252102407F55761444271AD43542ED465A808BE54679559819DF50487E54A999E6AF4EB93314FF2A0D3E41C39C6F1935804F8B3DA042FC84A992EA57FA7EE14C1F445219024013CA6A2BF3CD31E3978704E4F98173BA94B85EC6C9721B80267878B2ED32BF74511C526AE1E3629BC791B1C9CFACFAD54C191EE0EC5D64F095563DE21F187E210241009CBD67C085267DC4FB00F5A24EDA2D71A328CE30DBB86D165FC94D7BAABE8F593499006849F1D018FFEFB7880E8CAE02F3FC8C599EC47DA08730313B9E5E01E7"


class UserHistoryRequestJson(BaseModel):
    userKey: str
    supportUser: str


@router.post("/vpn/api/v1/support/getuserhistory")
async def get_user_history(body: UserHistoryRequestJson):
    user_key = body.userKey
    support_user = body.supportUser

    parts = user_key.split(";")
    first_part = parts[0]
    second_part = parts[1]
    user_key = Crypto.decrypt_aes(first_part, PRIVATE_KEY_STR, second_part)

    if user_key.startswith("00") and len(user_key) > 128:
        user_key = user_key[2:]

    r_user = SupportUserPojo()
    r_user.user = support_user
    r_user = await r_user.find()

    has_permission = (
        (r_user.privileges == Privileges.ADMIN and r_user.enabled_show)
        or (r_user.privileges == Privileges.SUPPORT and r_user.enabled_show)
    )

    if has_permission:
        invoice = InvoicePojo()
        invoice.user_id = user_key
        invoices_pojo = await invoice.find_all_by_user_id()

        invoices_json = []
        for inv in invoices_pojo:
            invoice_j = InvoiceJson(
                invoice_id=inv.invoice_id,
                user_id=inv.user_id,
                amount=inv.amount,
                currency=inv.currency,
                status=inv.status,
                pay_url=inv.pay_url,
                created=inv.created,
                updated=inv.updated,
                fk_operation_id=inv.fk_operation_id,
                p_email=inv.p_email,
                p_phone=inv.p_phone,
                payer_account=inv.payer_account,
                commission=inv.commission,
                plan=inv.plan,
            )
            invoices_json.append(invoice_j.to_dict())

        user = UserPojo()
        user.device_id = user_key
        user = await user.find()

        user_json = UserJson.from_pojo(user)

        return {
            "error": False,
            "message": "success",
            "userData": user_json.to_dict(),
            "invoices": invoices_json,
        }
    else:
        user = UserPojo()
        user_json = UserJson.from_pojo(user)

        return JSONResponse(
            status_code=401,
            content={
                "error": True,
                "message": "You do not have permission to view this user's history",
                "userData": user_json.to_dict(),
                "invoices": [],
            },
        )
