from typing import Optional
import time

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "awg_user_configs"

_index_created = False


class UserConfigPojo:
    """
    Кэш персональных AWG-конфигов: один документ на пару (user_id, ip_address).
    config — base64 клиентского .conf, выданного агентом на VPS.
    """

    def __init__(self):
        self.user_id: str = ""
        self.ip_address: str = ""
        self.peer_name: str = ""
        self.config: str = ""
        self.created_at: int = int(time.time() * 1000)
        self.updated_at: int = int(time.time() * 1000)

    @staticmethod
    async def get_collection():
        global _index_created
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        if not _index_created:
            await collection.create_index(
                [("user_id", 1), ("ip_address", 1)], unique=True
            )
            await collection.create_index([("ip_address", 1), ("peer_name", 1)])
            _index_created = True
        return collection

    def to_doc(self) -> dict:
        return {
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "peer_name": self.peer_name,
            "config": self.config,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @staticmethod
    def from_doc(doc: dict) -> "UserConfigPojo":
        c = UserConfigPojo()
        c.user_id = doc.get("user_id", "")
        c.ip_address = doc.get("ip_address", "")
        c.peer_name = doc.get("peer_name", "")
        c.config = doc.get("config", "")
        c.created_at = doc.get("created_at", 0)
        c.updated_at = doc.get("updated_at", 0)
        return c

    @staticmethod
    async def find_one(user_id: str, ip_address: str) -> Optional["UserConfigPojo"]:
        collection = await UserConfigPojo.get_collection()
        doc = await collection.find_one({"user_id": user_id, "ip_address": ip_address})
        return UserConfigPojo.from_doc(doc) if doc else None

    async def upsert(self) -> bool:
        collection = await self.get_collection()
        self.updated_at = int(time.time() * 1000)
        await collection.update_one(
            {"user_id": self.user_id, "ip_address": self.ip_address},
            {"$set": self.to_doc()},
            upsert=True,
        )
        return True

    @staticmethod
    async def delete_by_peer_names(ip_address: str, peer_names: list[str]) -> int:
        """Инвалидация кэша при удалении пиров на сервере (cleanup агента)."""
        collection = await UserConfigPojo.get_collection()
        result = await collection.delete_many(
            {"ip_address": ip_address, "peer_name": {"$in": peer_names}}
        )
        return result.deleted_count

    @staticmethod
    async def delete_by_server(ip_address: str) -> int:
        """Полная инвалидация кэша сервера (например, после переустановки VPS)."""
        collection = await UserConfigPojo.get_collection()
        result = await collection.delete_many({"ip_address": ip_address})
        return result.deleted_count
