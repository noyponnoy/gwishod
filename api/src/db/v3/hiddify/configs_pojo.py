from typing import Optional

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "configs_hiddify_v3"


class ConfigPojo:
    def __init__(self):
        self.server_ip_address: str = ""
        self.config: str = ""

    def to_doc(self) -> dict:
        return {
            "server_ip_address": self.server_ip_address,
            "config": self.config,
        }

    @staticmethod
    def from_doc(doc: dict) -> "ConfigPojo":
        c = ConfigPojo()
        c.server_ip_address = doc.get("server_ip_address", "")
        c.config = doc.get("config", "")
        return c


class ConfigsPojo:
    def __init__(self):
        self.tg_id: str = ""
        self.configs: ConfigPojo = ConfigPojo()

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "tg_id": self.tg_id,
            "configs": self.configs.to_doc(),
        }

    @staticmethod
    def from_doc(doc: dict) -> "ConfigsPojo":
        cp = ConfigsPojo()
        cp.tg_id = doc.get("tg_id", "")
        configs_raw = doc.get("configs", {})
        if isinstance(configs_raw, dict):
            cp.configs = ConfigPojo.from_doc(configs_raw)
        return cp

    async def find_all_by_tg_id(self) -> list[ConfigPojo]:
        collection = await self.get_collection()
        cursor = collection.find({"tg_id": self.tg_id})
        configs = []
        async for doc in cursor:
            cp = ConfigsPojo.from_doc(doc)
            configs.append(cp.configs)
        return configs

    async def insert(self) -> bool:
        collection = await self.get_collection()
        await collection.insert_one(self.to_doc())
        return True

    async def update(self) -> bool:
        # Stubbed out in Rust source (commented-out implementation)
        return True

    async def delete(self) -> bool:
        collection = await self.get_collection()
        await collection.delete_one({"tg_id": self.tg_id})
        return True
