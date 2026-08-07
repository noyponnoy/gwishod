from typing import Optional

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "tariff"


class TariffPojo:
    def __init__(self):
        self.name: str = "0"
        self.technical_name: str = "0"
        self.description: str = "0"
        self.price: float = 0.0
        self.enabled: bool = False
        self.duration: int = 0

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "name": self.name,
            "technicalName": self.technical_name,
            "description": self.description,
            "price": self.price,
            "enabled": self.enabled,
            "duration": self.duration,
        }

    @staticmethod
    def from_doc(doc: dict) -> "TariffPojo":
        t = TariffPojo()
        t.name = doc.get("name", "0")
        t.technical_name = doc.get("technicalName", "0")
        t.description = doc.get("description", "0")
        t.price = doc.get("price", 0.0)
        t.enabled = doc.get("enabled", False)
        t.duration = doc.get("duration", 0)
        return t

    @staticmethod
    async def is_exist(tname: str) -> bool:
        collection = await TariffPojo.get_collection()
        result = await collection.find_one({"technicalName": tname})
        return result is not None

    async def insert(self) -> bool:
        collection = await self.get_collection()
        if await self.is_exist(self.technical_name):
            return await self.update()
        await collection.insert_one(self.to_doc())
        return True

    async def update(self) -> bool:
        collection = await self.get_collection()
        await collection.update_one(
            {"technicalName": self.technical_name},
            {"$set": {
                "name": self.name,
                "technicalName": self.technical_name,
                "description": self.description,
                "price": self.price,
                "enabled": self.enabled,
                "duration": self.duration,
            }}
        )
        return True

    async def delete(self) -> bool:
        collection = await self.get_collection()
        await collection.delete_one({"technicalName": self.technical_name})
        return True

    async def find(self) -> Optional["TariffPojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"technicalName": self.technical_name})
        return TariffPojo.from_doc(doc) if doc else None

    @staticmethod
    async def find_all() -> list["TariffPojo"]:
        collection = await TariffPojo.get_collection()
        cursor = collection.find({})
        tariffs = []
        async for doc in cursor:
            tariffs.append(TariffPojo.from_doc(doc))
        return tariffs
