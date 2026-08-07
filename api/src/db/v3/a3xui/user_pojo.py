from typing import Optional
import uuid as uuid_module

import motor.motor_asyncio
from bson import ObjectId

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "users_3xui_v3"


class UserPojo:
    def __init__(self):
        self._id: Optional[ObjectId] = ObjectId()
        self.tg_id: str = "0"
        self.uuid: str = str(uuid_module.uuid4())
        self.device_id: str = "0"
        self.user_id: str = "0"
        self.expired_at: dict = {}
        self.free: bool = False
        self.litenotif3: bool = True
        self.litenotif2: bool = False
        self.litenotif1: bool = False
        self.litenotif0: bool = True
        self.pronotif3: bool = True
        self.pronotif2: bool = False
        self.pronotif1: bool = False
        self.pronotif0: bool = True
        self.delnotif: bool = False
        self.enable: dict = {"1": False, "2": False}

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "_id": self._id,
            "tg_id": self.tg_id,
            "uuid": self.uuid,
            "device_id": self.device_id,
            "user_id": self.user_id,
            "expired_at": self.expired_at,
            "free": self.free,
            "litenotif3": self.litenotif3,
            "litenotif2": self.litenotif2,
            "litenotif1": self.litenotif1,
            "litenotif0": self.litenotif0,
            "pronotif3": self.pronotif3,
            "pronotif2": self.pronotif2,
            "pronotif1": self.pronotif1,
            "pronotif0": self.pronotif0,
            "delnotif": self.delnotif,
            "enable": self.enable,
        }

    @staticmethod
    def from_doc(doc: dict) -> "UserPojo":
        u = UserPojo()
        u._id = doc.get("_id")
        u.tg_id = doc.get("tg_id", "0")
        u.uuid = doc.get("uuid", str(uuid_module.uuid4()))
        u.device_id = doc.get("device_id", "0")
        u.user_id = doc.get("user_id", "0")
        u.expired_at = doc.get("expired_at", {})
        u.free = doc.get("free", False)
        u.litenotif3 = doc.get("litenotif3", True)
        u.litenotif2 = doc.get("litenotif2", False)
        u.litenotif1 = doc.get("litenotif1", False)
        u.litenotif0 = doc.get("litenotif0", True)
        u.pronotif3 = doc.get("pronotif3", True)
        u.pronotif2 = doc.get("pronotif2", False)
        u.pronotif1 = doc.get("pronotif1", False)
        u.pronotif0 = doc.get("pronotif0", True)
        u.delnotif = doc.get("delnotif", False)
        u.enable = doc.get("enable", {"1": False, "2": False})
        return u

    async def is_exist(self) -> bool:
        collection = await self.get_collection()
        result = await collection.find_one({"tg_id": self.tg_id})
        return result is not None

    async def insert(self) -> bool:
        collection = await self.get_collection()
        await collection.insert_one(self.to_doc())
        return True

    async def update(self) -> bool:
        collection = await self.get_collection()
        await collection.update_one(
            {"tg_id": self.tg_id},
            {"$set": {
                "device_id": self.device_id,
                "user_id": self.user_id,
                "expired_at": self.expired_at,
                "uuid": self.uuid,
                "free": self.free,
                "litenotif3": self.litenotif3,
                "litenotif2": self.litenotif2,
                "litenotif1": self.litenotif1,
                "litenotif0": self.litenotif0,
                "pronotif3": self.pronotif3,
                "pronotif2": self.pronotif2,
                "pronotif1": self.pronotif1,
                "pronotif0": self.pronotif0,
                "delnotif": self.delnotif,
                "enable": self.enable,
            }}
        )
        return True

    async def delete(self) -> bool:
        collection = await self.get_collection()
        await collection.delete_one({"tg_id": self.tg_id})
        return True

    @staticmethod
    async def find_all() -> list["UserPojo"]:
        collection = await UserPojo.get_collection()
        cursor = collection.find({})
        users = []
        async for doc in cursor:
            users.append(UserPojo.from_doc(doc))
        return users

    async def find(self) -> "UserPojo":
        collection = await self.get_collection()
        doc = await collection.find_one({"tg_id": self.tg_id})
        return UserPojo.from_doc(doc) if doc else UserPojo()
