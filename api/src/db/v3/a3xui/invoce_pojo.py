from typing import Optional

import motor.motor_asyncio
from bson import ObjectId

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "invoices_3xui_v3"


class InvoicePojo:
    def __init__(self):
        self._id: Optional[ObjectId] = ObjectId()
        self.invoice_id: str = ""
        self.tg_id: str = ""
        self.invoice_amount: str = ""
        self.tariff_name: str = ""
        self.paid: bool = False

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "_id": self._id,
            "invoice_id": self.invoice_id,
            "tg_id": self.tg_id,
            "invoice_amount": self.invoice_amount,
            "tariff_name": self.tariff_name,
            "paid": self.paid,
        }

    @staticmethod
    def from_doc(doc: dict) -> "InvoicePojo":
        inv = InvoicePojo()
        inv._id = doc.get("_id")
        inv.invoice_id = doc.get("invoice_id", "")
        inv.tg_id = doc.get("tg_id", "")
        inv.invoice_amount = doc.get("invoice_amount", "")
        inv.tariff_name = doc.get("tariff_name", "")
        inv.paid = doc.get("paid", False)
        return inv

    async def insert(self) -> bool:
        collection = await self.get_collection()
        await collection.insert_one(self.to_doc())
        return True

    async def find(self) -> "InvoicePojo":
        collection = await self.get_collection()
        doc = await collection.find_one({"invoice_id": self.invoice_id})
        return InvoicePojo.from_doc(doc) if doc else InvoicePojo()

    async def update(self) -> bool:
        collection = await self.get_collection()
        await collection.update_one(
            {"invoice_id": self.invoice_id},
            {"$set": {
                "_id": self._id,
                "tg_id": self.tg_id,
                "invoice_amount": self.invoice_amount,
                "tariff_name": self.tariff_name,
                "paid": self.paid,
            }}
        )
        return True

    @staticmethod
    async def find_all() -> list["InvoicePojo"]:
        collection = await InvoicePojo.get_collection()
        cursor = collection.find({})
        invoices = []
        async for doc in cursor:
            invoices.append(InvoicePojo.from_doc(doc))
        return invoices
