from typing import Optional

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "invoices_v3"


class InvoicePojo:
    def __init__(self):
        self.invoice_id: str = ""
        self.operation_id: str = ""
        self.user_id: str = ""
        self.amount: str = ""
        self.status: bool = False
        self.pay_url: str = ""
        self.created: int = 0
        self.updated: int = 0
        self.p_email: str = ""
        self.p_phone: str = ""
        self.commission: str = ""
        self.plan: str = ""

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "invoice_id": self.invoice_id,
            "operation_id": self.operation_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "status": self.status,
            "pay_url": self.pay_url,
            "created": self.created,
            "updated": self.updated,
            "p_email": self.p_email,
            "p_phone": self.p_phone,
            "commission": self.commission,
            "plan": self.plan,
        }

    @staticmethod
    def from_doc(doc: dict) -> "InvoicePojo":
        inv = InvoicePojo()
        inv.invoice_id = doc.get("invoice_id", "")
        inv.operation_id = doc.get("operation_id", "")
        inv.user_id = doc.get("user_id", "")
        inv.amount = doc.get("amount", "")
        inv.status = doc.get("status", False)
        inv.pay_url = doc.get("pay_url", "")
        inv.created = doc.get("created", 0)
        inv.updated = doc.get("updated", 0)
        inv.p_email = doc.get("p_email", "")
        inv.p_phone = doc.get("p_phone", "")
        inv.commission = doc.get("commission", "")
        inv.plan = doc.get("plan", "")
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
        await collection.update_one(
            {"invoiceId": self.invoice_id},
            {"$set": {
                "user_id": self.user_id,
                "operation_id": self.operation_id,
                "amount": self.amount,
                "pay_url": self.pay_url,
                "created": self.created,
                "updated": self.updated,
                "p_email": self.p_email,
                "p_phone": self.p_phone,
                "commission": self.commission,
                "plan": self.plan,
            }}
        )
        return True

    async def find_by_id(self) -> Optional["InvoicePojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"invoice_id": self.invoice_id})
        return InvoicePojo.from_doc(doc) if doc else None

    async def find_all_by_user_id(self) -> list["InvoicePojo"]:
        collection = await self.get_collection()
        cursor = collection.find({"user_id": self.user_id})
        invoices = []
        async for doc in cursor:
            invoices.append(InvoicePojo.from_doc(doc))
        return invoices
