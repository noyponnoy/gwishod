from typing import Optional

import motor.motor_asyncio

from src.db.v1.privileges import Privileges

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "supportusers"


class SupportUserPojo:
    def __init__(self):
        self.user: str = "0"
        self.enabled_show: bool = False
        self.enabled_update: bool = False
        self.privileges: Privileges = Privileges.SUPPORT

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "user": self.user,
            "enabledshow": self.enabled_show,
            "enabledupdate": self.enabled_update,
            "privileges": self.privileges.value,
        }

    @staticmethod
    def from_doc(doc: dict) -> "SupportUserPojo":
        sup = SupportUserPojo()
        sup.user = doc.get("user", "0")
        sup.enabled_show = doc.get("enabledshow", False)
        sup.enabled_update = doc.get("enabledupdate", False)
        priv_str = doc.get("privileges", "SUPPORT")
        sup.privileges = Privileges(priv_str) if priv_str in Privileges.__members__ else Privileges.SUPPORT
        return sup

    @staticmethod
    async def is_exist(user: str) -> bool:
        collection = await SupportUserPojo.get_collection()
        result = await collection.find_one({"user": user})
        return result is not None

    async def insert(self) -> bool:
        collection = await self.get_collection()
        if await self.is_exist(self.user):
            return await self.update()
        await collection.insert_one(self.to_doc())
        return True

    async def update(self) -> bool:
        collection = await self.get_collection()
        await collection.update_one(
            {"user": self.user},
            {"$set": {
                "enabledshow": self.enabled_show,
                "enabledupdate": self.enabled_update,
                "priveleges": self.privileges.value,
            }}
        )
        return True

    async def find(self) -> Optional["SupportUserPojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"user": self.user})
        return SupportUserPojo.from_doc(doc) if doc else None
