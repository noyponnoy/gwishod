from typing import Optional
import time

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "servers_awg"


class ServerPojo:
    def __init__(self):
        self.country: str = "0"
        self.ip_address: str = "0"
        self.recommend: bool = False
        self.priority: int = 0
        self.config: str = "0" # Base64 of the .conf file or client config string
        self.created_at: int = int(time.time() * 1000)
        self.premium: bool = False
        self.state: str = "0"
        self.status: bool = False
        self.country_code: str = "0"

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "country": self.country,
            "ip_address": self.ip_address,
            "recommend": self.recommend,
            "priority": self.priority,
            "config": self.config,
            "created_at": self.created_at,
            "premium": self.premium,
            "state": self.state,
            "status": self.status,
            "country_code": self.country_code,
        }

    @staticmethod
    def from_doc(doc: dict) -> "ServerPojo":
        s = ServerPojo()
        s.country = doc.get("country", "0")
        s.ip_address = doc.get("ip_address", "0")
        s.recommend = doc.get("recommend", False)
        s.priority = doc.get("priority", 0)
        s.config = doc.get("config", "0")
        s.created_at = doc.get("created_at", 0)
        s.premium = doc.get("premium", False)
        s.state = doc.get("state", "0")
        s.status = doc.get("status", False)
        s.country_code = doc.get("country_code", "0")
        return s

    @staticmethod
    async def is_exist(ip_address: str) -> bool:
        collection = await ServerPojo.get_collection()
        result = await collection.find_one({"ip_address": ip_address})
        return result is not None

    async def insert(self) -> bool:
        collection = await self.get_collection()
        if await self.is_exist(self.ip_address):
            return await self.update()
        await collection.insert_one(self.to_doc())
        return True

    async def update(self) -> bool:
        collection = await self.get_collection()
        await collection.update_one(
            {"ip_address": self.ip_address},
            {"$set": {
                "country": self.country,
                "recommend": self.recommend,
                "priority": self.priority,
                "config": self.config,
                "created_at": self.created_at,
                "premium": self.premium,
                "state": self.state,
                "status": self.status,
                "country_code": self.country_code,
            }}
        )
        return True

    async def find(self) -> Optional["ServerPojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"ip_address": self.ip_address})
        return ServerPojo.from_doc(doc) if doc else None

    @staticmethod
    async def find_all() -> list["ServerPojo"]:
        collection = await ServerPojo.get_collection()
        cursor = collection.find({})
        servers = []
        async for doc in cursor:
            servers.append(ServerPojo.from_doc(doc))
        return servers

    async def delete(self) -> bool:
        collection = await self.get_collection()
        await collection.delete_one({"ip_address": self.ip_address})
        return True
