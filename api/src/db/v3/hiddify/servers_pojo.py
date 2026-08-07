from typing import Optional

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "servers_hiddify_v3"


class ServerPojo:
    def __init__(self):
        self.country: str = "0"
        self.ip_address: str = "0"
        self.server_address: str = ""
        self.path: str = ""
        self.path_user: str = ""
        self.admin_uuid: str = ""
        self.premium: bool = False
        self.enabled: bool = False
        self.price: int = 0

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "country": self.country,
            "ip_address": self.ip_address,
            "server_address": self.server_address,
            "path": self.path,
            "path_user": self.path_user,
            "admin_uuid": self.admin_uuid,
            "premium": self.premium,
            "enabled": self.enabled,
            "price": self.price,
        }

    @staticmethod
    def from_doc(doc: dict) -> "ServerPojo":
        s = ServerPojo()
        s.country = doc.get("country", "0")
        s.ip_address = doc.get("ip_address", "0")
        s.server_address = doc.get("server_address", "")
        s.path = doc.get("path", "")
        s.path_user = doc.get("path_user", "")
        s.admin_uuid = doc.get("admin_uuid", "")
        s.premium = doc.get("premium", False)
        s.enabled = doc.get("enabled", False)
        s.price = doc.get("price", 0)
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
                "premium": self.premium,
                "enabled": self.enabled,
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

    @staticmethod
    async def find_with_premium() -> list["ServerPojo"]:
        collection = await ServerPojo.get_collection()
        cursor = collection.find({"premium": True})
        servers = []
        async for doc in cursor:
            servers.append(ServerPojo.from_doc(doc))
        return servers

    @staticmethod
    async def all_without_premium() -> list["ServerPojo"]:
        collection = await ServerPojo.get_collection()
        cursor = collection.find({"premium": False})
        servers = []
        async for doc in cursor:
            s = ServerPojo.from_doc(doc)
            if s.enabled:
                servers.append(s)
        return servers

    async def delete(self) -> bool:
        collection = await self.get_collection()
        await collection.delete_one({"ip_address": self.ip_address})
        return True
