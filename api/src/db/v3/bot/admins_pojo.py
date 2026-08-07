from typing import Optional

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "admins_bot_v3"


class AdminsPojo:
    def __init__(self):
        self.user_id: str = ""
        self.log_level: str = ""
        self.room_id: str = ""

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "user_id": self.user_id,
            "log_level": self.log_level,
            "room_id": self.room_id,
        }

    @staticmethod
    def from_doc(doc: dict) -> "AdminsPojo":
        a = AdminsPojo()
        a.user_id = doc.get("user_id", "")
        a.log_level = doc.get("log_level", "")
        a.room_id = doc.get("room_id", "")
        return a

    async def is_exist(self) -> bool:
        return (await self.find_by_user_id()) is not None

    async def insert(self) -> bool:
        collection = await self.get_collection()
        result = await collection.insert_one(self.to_doc())
        return bool(result.inserted_id)

    async def find_by_user_id(self) -> Optional["AdminsPojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"user_id": self.user_id})
        return AdminsPojo.from_doc(doc) if doc else None

    async def update(self) -> bool:
        collection = await self.get_collection()
        result = await collection.update_one(
            {"user_id": self.user_id},
            {"$set": {
                "log_level": self.log_level,
                "room_id": self.room_id,
            }}
        )
        return result.modified_count > 0

    @staticmethod
    async def get_all() -> list["AdminsPojo"]:
        collection = await AdminsPojo.get_collection()
        cursor = collection.find({})
        admins = []
        async for doc in cursor:
            admins.append(AdminsPojo.from_doc(doc))
        return admins
