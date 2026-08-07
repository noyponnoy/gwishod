import base64
import hashlib
import time
from typing import Optional

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "admins_v3"


class AdminPojo:
    def __init__(self):
        self.login: str = ""
        self.hash: str = ""
        self.token: str = ""
        self.expire: int = 0

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "login": self.login,
            "hash": self.hash,
            "token": self.token,
            "expire": self.expire,
        }

    @staticmethod
    def from_doc(doc: dict) -> "AdminPojo":
        a = AdminPojo()
        a.login = doc.get("login", "")
        a.hash = doc.get("hash", "")
        a.token = doc.get("token", "")
        a.expire = doc.get("expire", 0)
        return a

    async def is_exist(self) -> bool:
        return (await self.find_by_login()) is not None

    async def find_by_login(self) -> Optional["AdminPojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"login": self.login})
        return AdminPojo.from_doc(doc) if doc else None

    async def find_by_token(self) -> Optional["AdminPojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"token": self.token})
        return AdminPojo.from_doc(doc) if doc else None

    @staticmethod
    async def find_all() -> list["AdminPojo"]:
        collection = await AdminPojo.get_collection()
        cursor = collection.find({})
        admins = []
        async for doc in cursor:
            admins.append(AdminPojo.from_doc(doc))
        return admins

    async def insert(self) -> bool:
        collection = await self.get_collection()
        result = await collection.insert_one(self.to_doc())
        return bool(result.inserted_id)

    async def update(self) -> bool:
        collection = await self.get_collection()
        result = await collection.replace_one(
            {"login": self.login},
            self.to_doc(),
        )
        return result.modified_count > 0

    async def delete(self) -> bool:
        collection = await self.get_collection()
        result = await collection.delete_one({"login": self.login})
        return result.deleted_count > 0

    async def check_token(self) -> bool:
        current_time_millis = int(time.time() * 1000)
        if self.expire >= current_time_millis:
            self.expire = current_time_millis + 900000
            await self.update()
            return True
        return False

    async def check_password(self, password: str) -> bool:
        computed = base64.b64encode(
            hashlib.sha256(
                password.encode("utf-8") + self.login.encode("utf-8")
            ).digest()
        ).decode("utf-8")
        return computed == self.hash
