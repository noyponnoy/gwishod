from datetime import datetime, timezone
from typing import Optional

import motor.motor_asyncio
from pydantic import BaseModel, Field

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "servers"


class ServerJson(BaseModel):
    """JSON response model for server data (uses 'id' instead of '_id')."""
    id: str = "0"
    country: str = "0"
    ip_address: str = Field(default="0", alias="ipAddress")
    recommend: bool = False
    priority: int = 0
    u_nsm: str = "0"
    p_nsm: str = "0"
    ca_file_name: str = Field(default="0", alias="caFileName")
    ca_file: str = Field(default="0", alias="caFile")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="createdAt")
    premium: bool = False
    country_code: str = Field(default="0", alias="countryCode")
    state: str = "0"
    status: bool = False

    model_config = {"populate_by_name": True}

    def to_dict(self) -> dict:
        return self.model_dump(by_alias=True)

    @staticmethod
    def from_pojo(pojo: "ServerPojo") -> "ServerJson":
        return ServerJson(
            id=pojo.id, country=pojo.country, ip_address=pojo.ip_address,
            recommend=pojo.recommend, priority=pojo.priority,
            u_nsm=pojo.u_nsm, p_nsm=pojo.p_nsm,
            ca_file_name=pojo.ca_file_name, ca_file=pojo.ca_file,
            created_at=pojo.created_at,
            premium=pojo.premium, country_code=pojo.country_code,
            state=pojo.state, status=pojo.status,
        )


class ServerPojo:
    def __init__(self, **kwargs):
        self.id: str = kwargs.get("id", "0")
        self.country: str = kwargs.get("country", "0")
        self.ip_address: str = kwargs.get("ip_address", "0")
        self.recommend: bool = kwargs.get("recommend", False)
        self.priority: int = kwargs.get("priority", 0)
        self.u_nsm: str = kwargs.get("u_nsm", "0")
        self.p_nsm: str = kwargs.get("p_nsm", "0")
        self.ca_file_name: str = kwargs.get("ca_file_name", "0")
        self.ca_file: str = kwargs.get("ca_file", "0")
        self.created_at: datetime = kwargs.get("created_at", datetime.now(timezone.utc))
        self.premium: bool = kwargs.get("premium", False)
        self.country_code: str = kwargs.get("country_code", "0")
        self.state: str = kwargs.get("state", "0")
        self.status: bool = kwargs.get("status", False)

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "_id": self.id,
            "country": self.country,
            "ipAddress": self.ip_address,
            "recommend": self.recommend,
            "priority": self.priority,
            "u_nsm": self.u_nsm,
            "p_nsm": self.p_nsm,
            "caFileName": self.ca_file_name,
            "caFile": self.ca_file,
            "createdAt": self.created_at,
            "premium": self.premium,
            "countryCode": self.country_code,
            "state": self.state,
            "status": self.status,
        }

    @staticmethod
    def from_doc(doc: dict) -> "ServerPojo":
        server = ServerPojo()
        server.id = doc.get("_id", "0")
        server.country = doc.get("country", "0")
        server.ip_address = doc.get("ipAddress", "0")
        server.recommend = doc.get("recommend", False)
        server.priority = doc.get("priority", 0)
        server.u_nsm = doc.get("u_nsm", "0")
        server.p_nsm = doc.get("p_nsm", "0")
        server.ca_file_name = doc.get("caFileName", "0")
        server.ca_file = doc.get("caFile", "0")
        server.created_at = doc.get("createdAt", datetime.now(timezone.utc))
        server.premium = doc.get("premium", False)
        server.country_code = doc.get("countryCode", "0")
        server.state = doc.get("state", "0")
        server.status = doc.get("status", False)
        return server

    @staticmethod
    async def is_exist(ip_address: str) -> bool:
        collection = await ServerPojo.get_collection()
        result = await collection.find_one({"ipAddress": ip_address})
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
            {"ipAddress": self.ip_address},
            {"$set": {
                "country": self.country,
                "recommend": self.recommend,
                "priority": self.priority,
                "u_nsm": self.u_nsm,
                "p_nsm": self.p_nsm,
                "caFileName": self.ca_file_name,
                "caFile": self.ca_file,
                "createdAt": self.created_at,
                "premium": self.premium,
                "countryCode": self.country_code,
                "state": self.state,
                "status": self.status,
            }}
        )
        return True

    async def find(self) -> Optional["ServerPojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"ipAddress": self.ip_address})
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
        await collection.delete_one({"ipAddress": self.ip_address})
        return True

    @staticmethod
    async def find_all_with_premium() -> list["ServerPojo"]:
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
            servers.append(ServerPojo.from_doc(doc))
        premium_servers = await ServerPojo.find_all_with_premium()
        for ps in premium_servers:
            tmp = ServerPojo()
            tmp.__dict__ = ps.__dict__.copy()
            tmp.u_nsm = ""
            tmp.p_nsm = ""
            tmp.ca_file_name = ""
            tmp.ca_file = ""
            servers.append(tmp)
        return servers
