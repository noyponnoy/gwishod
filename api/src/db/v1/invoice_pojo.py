from datetime import datetime, timezone
from typing import Optional

import motor.motor_asyncio
from pydantic import BaseModel, Field

from src.db.v1.invoice_currency import InvoiceCurrency
from src.db.v1.invoice_status import InvoiceStatus

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "invoices"

DATE_FORMAT = "%a %b %d %H:%M:%S %Z %Y"


class InvoiceJson(BaseModel):
    """JSON response model with formatted date strings (timezone-aware)."""
    invoice_id: str = Field(default="0", alias="invoiceId")
    user_id: str = Field(default="0", alias="userId")
    amount: str = "0"
    currency: str = "VISARUB"
    status: str = "CREATED"
    pay_url: str = Field(default="0", alias="payUrl")
    created: str = ""
    updated: str = ""
    fk_operation_id: str = Field(default="0", alias="FKoperationId")
    p_email: str = Field(default="0", alias="P_EMAIL")
    p_phone: str = Field(default="0", alias="P_PHONE")
    payer_account: str = Field(default="0", alias="payerAccount")
    commission: str = "0"
    plan: str = "0"

    model_config = {"populate_by_name": True}

    def to_dict(self) -> dict:
        return self.model_dump(by_alias=True)

    @staticmethod
    def from_pojo(pojo: "InvoicePojo") -> "InvoiceJson":
        fmt = lambda dt: dt.strftime(DATE_FORMAT) if isinstance(dt, datetime) else str(dt)
        return InvoiceJson(
            invoice_id=pojo.invoice_id, user_id=pojo.user_id,
            amount=pojo.amount, currency=pojo.currency.value,
            status=pojo.status.value, pay_url=pojo.pay_url,
            created=fmt(pojo.created), updated=fmt(pojo.updated),
            fk_operation_id=pojo.fk_operation_id, p_email=pojo.p_email,
            p_phone=pojo.p_phone, payer_account=pojo.payer_account,
            commission=pojo.commission, plan=pojo.plan,
        )


class InvoiceJson2(BaseModel):
    """JSON response/request model with formatted date strings (naive dates)."""
    invoice_id: str = Field(default="0", alias="invoiceId")
    user_id: str = Field(default="0", alias="userId")
    amount: str = "0"
    currency: str = "VISARUB"
    status: str = "CREATED"
    pay_url: str = Field(default="0", alias="payUrl")
    created: str = ""
    updated: str = ""
    fk_operation_id: str = Field(default="0", alias="FKoperationId")
    p_email: str = Field(default="0", alias="P_EMAIL")
    p_phone: str = Field(default="0", alias="P_PHONE")
    payer_account: str = Field(default="0", alias="payerAccount")
    commission: str = "0"
    plan: str = "0"

    model_config = {"populate_by_name": True}

    def to_dict(self) -> dict:
        return self.model_dump(by_alias=True)


class InvoicePojo:
    def __init__(self, **kwargs):
        self.invoice_id: str = kwargs.get("invoice_id", "0")
        self.user_id: str = kwargs.get("user_id", "0")
        self.amount: str = kwargs.get("amount", "0")
        self.currency: InvoiceCurrency = kwargs.get("currency", InvoiceCurrency.VISARUB)
        self.status: InvoiceStatus = kwargs.get("status", InvoiceStatus.CREATED)
        self.pay_url: str = kwargs.get("pay_url", "0")
        self.created: datetime = kwargs.get("created", datetime.now(timezone.utc))
        self.updated: datetime = kwargs.get("updated", datetime.now(timezone.utc))
        self.fk_operation_id: str = kwargs.get("fk_operation_id", "0")
        self.p_email: str = kwargs.get("p_email", "0")
        self.p_phone: str = kwargs.get("p_phone", "0")
        self.payer_account: str = kwargs.get("payer_account", "0")
        self.commission: str = kwargs.get("commission", "0")
        self.plan: str = kwargs.get("plan", "0")

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        currency_val = self.currency.value if hasattr(self.currency, "value") else str(self.currency)
        status_val = self.status.value if hasattr(self.status, "value") else str(self.status)
        return {
            "invoiceId": self.invoice_id,
            "userId": self.user_id,
            "amount": self.amount,
            "currency": currency_val,
            "status": status_val,
            "payUrl": self.pay_url,
            "created": self.created,
            "updated": self.updated,
            "FKoperationId": self.fk_operation_id,
            "P_EMAIL": self.p_email,
            "P_PHONE": self.p_phone,
            "payerAccount": self.payer_account,
            "commission": self.commission,
            "plan": self.plan,
        }

    @staticmethod
    def from_doc(doc: dict) -> "InvoicePojo":
        inv = InvoicePojo()
        inv.invoice_id = doc.get("invoiceId", "0")
        inv.user_id = doc.get("userId", "0")
        inv.amount = doc.get("amount", "0")
        currency_str = doc.get("currency", "VISARUB")
        try:
            inv.currency = InvoiceCurrency(currency_str)
        except ValueError:
            inv.currency = InvoiceCurrency.other
        status_str = doc.get("status", "CREATED")
        try:
            inv.status = InvoiceStatus(status_str)
        except ValueError:
            inv.status = InvoiceStatus.CREATED
        inv.pay_url = doc.get("payUrl", "0")
        inv.created = doc.get("created", datetime.now(timezone.utc))
        inv.updated = doc.get("updated", datetime.now(timezone.utc))
        inv.fk_operation_id = doc.get("FKoperationId", "0")
        inv.p_email = doc.get("P_EMAIL", "0")
        inv.p_phone = doc.get("P_PHONE", "0")
        inv.payer_account = doc.get("payerAccount", "0")
        inv.commission = doc.get("commission", "0")
        inv.plan = doc.get("plan", "0")
        return inv

    @staticmethod
    async def is_exist(invoice_id: str) -> bool:
        collection = await InvoicePojo.get_collection()
        result = await collection.find_one({"invoiceId": invoice_id})
        return result is not None

    async def insert(self) -> bool:
        collection = await self.get_collection()
        if await self.is_exist(self.invoice_id):
            return await self.update()
        await collection.insert_one(self.to_doc())
        return True

    async def update(self) -> bool:
        collection = await self.get_collection()
        currency_val = self.currency.value if hasattr(self.currency, "value") else str(self.currency)
        status_val = self.status.value if hasattr(self.status, "value") else str(self.status)
        await collection.update_one(
            {"invoiceId": self.invoice_id},
            {"$set": {
                "userId": self.user_id,
                "amount": self.amount,
                "currency": currency_val,
                "status": status_val,
                "payUrl": self.pay_url,
                "created": self.created,
                "updated": self.updated,
                "FKoperationId": self.fk_operation_id,
                "P_EMAIL": self.p_email,
                "P_PHONE": self.p_phone,
                "payerAccount": self.payer_account,
                "commission": self.commission,
                "plan": self.plan,
            }}
        )
        return True

    async def find_by_id(self) -> Optional["InvoicePojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"invoiceId": self.invoice_id})
        return InvoicePojo.from_doc(doc) if doc else None

    async def find_all_by_user_id(self) -> list["InvoicePojo"]:
        collection = await self.get_collection()
        cursor = collection.find({"userId": self.user_id})
        invoices = []
        async for doc in cursor:
            invoices.append(InvoicePojo.from_doc(doc))
        return invoices
