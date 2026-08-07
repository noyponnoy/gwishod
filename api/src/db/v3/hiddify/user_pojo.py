from typing import Optional

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "users_hiddify_v3"


class UserPojo:
    def __init__(self):
        self.user_id: str = "0"
        self.device_id: str = "0"
        self.tg_id: str = "0"

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "user_id": self.user_id,
            "device_id": self.device_id,
            "tg_id": self.tg_id,
        }

    @staticmethod
    def from_doc(doc: dict) -> "UserPojo":
        u = UserPojo()
        u.user_id = doc.get("user_id", "0")
        u.device_id = doc.get("device_id", "0")
        u.tg_id = doc.get("tg_id", "0")
        return u

    async def is_exist(self) -> bool:
        return (await self.find_by_tg_id()) is not None

    async def find_by_user_id(self) -> Optional["UserPojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"user_id": self.user_id})
        return UserPojo.from_doc(doc) if doc else None

    async def insert(self) -> bool:
        collection = await self.get_collection()
        await collection.insert_one(self.to_doc())
        return True

    async def delete(self) -> bool:
        collection = await self.get_collection()
        result = await collection.delete_one({"tg_id": self.tg_id})
        return result.deleted_count > 0

    async def update(self) -> bool:
        collection = await self.get_collection()
        result = await collection.update_one(
            {"tg_id": self.tg_id},
            {"$set": {
                "user_id": self.user_id,
                "device_id": self.device_id,
            }}
        )
        return result.modified_count > 0

    async def find_by_device_id(self) -> Optional["UserPojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"device_id": self.device_id})
        return UserPojo.from_doc(doc) if doc else None

    async def find_by_tg_id(self) -> Optional["UserPojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"tg_id": self.tg_id})
        return UserPojo.from_doc(doc) if doc else None
