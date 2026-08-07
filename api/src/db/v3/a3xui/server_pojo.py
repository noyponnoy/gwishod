from typing import Optional

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "servers_3xui_v3"


class ServerPojo:
    def __init__(self):
        self.server_ip: str = "0"
        self.server_domain_port_path: str = "0"
        self.server_domain_port_path_sub: str = "0"
        self.login: str = "0"
        self.password: str = "0"
        self.session: str = "0"
        self.t_name: int = 0
        self.description: str = "0"

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "server_ip": self.server_ip,
            "server_domain_port_path": self.server_domain_port_path,
            "server_domain_port_path_sub": self.server_domain_port_path_sub,
            "login": self.login,
            "password": self.password,
            "session": self.session,
            "t_name": self.t_name,
            "description": self.description,
        }

    @staticmethod
    def from_doc(doc: dict) -> "ServerPojo":
        s = ServerPojo()
        s.server_ip = doc.get("server_ip", "0")
        s.server_domain_port_path = doc.get("server_domain_port_path", "0")
        s.server_domain_port_path_sub = doc.get("server_domain_port_path_sub", "0")
        s.login = doc.get("login", "0")
        s.password = doc.get("password", "0")
        s.session = doc.get("session", "0")
        s.t_name = doc.get("t_name", 0)
        s.description = doc.get("description", "0")
        return s

    async def is_exist(self) -> bool:
        collection = await self.get_collection()
        result = await collection.find_one({"server_ip": self.server_ip})
        return result is not None

    async def insert(self) -> bool:
        collection = await self.get_collection()
        await collection.insert_one(self.to_doc())
        return True

    async def find_by_ip(self) -> "ServerPojo":
        collection = await self.get_collection()
        doc = await collection.find_one({"server_ip": self.server_ip})
        return ServerPojo.from_doc(doc) if doc else ServerPojo()

    async def update_by_ip(self) -> bool:
        collection = await self.get_collection()
        await collection.update_one(
            {"server_ip": self.server_ip},
            {"$set": {
                "login": self.login,
                "server_domain_port_path": self.server_domain_port_path,
                "server_domain_port_path_sub": self.server_domain_port_path_sub,
                "password": self.password,
                "session": self.session,
                "t_name": self.t_name,
                "description": self.description,
            }}
        )
        return True

    async def update(self) -> bool:
        return await self.update_by_ip()

    async def delete(self) -> bool:
        collection = await self.get_collection()
        await collection.delete_one({"server_ip": self.server_ip})
        return True

    @staticmethod
    async def find_all() -> list["ServerPojo"]:
        collection = await ServerPojo.get_collection()
        cursor = collection.find({})
        servers = []
        async for doc in cursor:
            servers.append(ServerPojo.from_doc(doc))
        return servers
