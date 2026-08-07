from typing import Optional

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "code_v3"


class CodePojo:
    def __init__(self):
        self.code: str = ""
        self.user_id: str = ""
        self.user_used_id: str = ""
        self.used: bool = False
        self.created: int = 0
        self.purchased: int = 0
        self.used_date: int = 0
        self.duration: int = 0
        self.pay_url: str = ""

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "code": self.code,
            "user_id": self.user_id,
            "user_used_id": self.user_used_id,
            "used": self.used,
            "created": self.created,
            "purchased": self.purchased,
            "used_date": self.used_date,
            "duration": self.duration,
            "pay_url": self.pay_url,
        }

    @staticmethod
    def from_doc(doc: dict) -> "CodePojo":
        c = CodePojo()
        c.code = doc.get("code", "")
        c.user_id = doc.get("user_id", "")
        c.user_used_id = doc.get("user_used_id", "")
        c.used = doc.get("used", False)
        c.created = doc.get("created", 0)
        c.purchased = doc.get("purchased", 0)
        c.used_date = doc.get("used_date", 0)
        c.duration = doc.get("duration", 0)
        c.pay_url = doc.get("pay_url", "")
        return c

    async def is_exist(self) -> bool:
        collection = await self.get_collection()
        result = await collection.find_one({"code": self.code})
        return result is not None

    async def insert(self) -> bool:
        collection = await self.get_collection()
        if await self.is_exist():
            return False
        await collection.insert_one(self.to_doc())
        return True

    async def update(self) -> bool:
        collection = await self.get_collection()
        await collection.update_one(
            {"code": self.code},
            {"$set": {
                "user_id": self.user_id,
                "user_used_id": self.user_used_id,
                "used": self.used,
                "created": self.created,
                "purchased": self.purchased,
                "used_date": self.used_date,
                "duration": self.duration,
                "pay_url": self.pay_url,
            }}
        )
        return True

    async def delete(self) -> bool:
        collection = await self.get_collection()
        await collection.delete_one({"code": self.code})
        return True

    async def find_by_code(self) -> Optional["CodePojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"code": self.code})
        return CodePojo.from_doc(doc) if doc else None

    async def find_by_user_id(self) -> list["CodePojo"]:
        collection = await self.get_collection()
        cursor = collection.find({"user_id": self.user_id})
        codes = []
        async for doc in cursor:
            codes.append(CodePojo.from_doc(doc))
        return codes

    @staticmethod
    async def find_all() -> list["CodePojo"]:
        collection = await CodePojo.get_collection()
        cursor = collection.find({})
        codes = []
        async for doc in cursor:
            codes.append(CodePojo.from_doc(doc))
        return codes
