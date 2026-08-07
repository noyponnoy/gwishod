from typing import Optional

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "users_v3"


class UserPojo:
    def __init__(self):
        self.user_id: str = ""
        self.total_download: int = 0
        self.total_upload: int = 0
        self.source_ip: str = ""
        self.created_at: int = 0
        self.last_login: int = 0
        self.is_premium: bool = False
        self.premium_end: int = 0

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "user_id": self.user_id,
            "total_download": self.total_download,
            "total_upload": self.total_upload,
            "source_ip": self.source_ip,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "is_premium": self.is_premium,
            "premium_end": self.premium_end,
        }

    @staticmethod
    def from_doc(doc: dict) -> "UserPojo":
        u = UserPojo()
        u.user_id = doc.get("user_id", "")
        u.total_download = doc.get("total_download", 0)
        u.total_upload = doc.get("total_upload", 0)
        u.source_ip = doc.get("source_ip", "")
        u.created_at = doc.get("created_at", 0)
        u.last_login = doc.get("last_login", 0)
        u.is_premium = doc.get("is_premium", False)
        u.premium_end = doc.get("premium_end", 0)
        return u

    async def is_exist(self) -> bool:
        return (await self.find_by_user_id()) is not None

    async def find_by_user_id(self) -> Optional["UserPojo"]:
        collection = await self.get_collection()
        doc = await collection.find_one({"user_id": self.user_id})
        return UserPojo.from_doc(doc) if doc else None

    @staticmethod
    async def find_by_premium(user: "UserPojo") -> list["UserPojo"]:
        collection = await UserPojo.get_collection()
        cursor = collection.find({"is_premium": user.is_premium})
        users = []
        async for doc in cursor:
            users.append(UserPojo.from_doc(doc))
        return users

    async def find_by_premium_end_after(self) -> list["UserPojo"]:
        collection = await self.get_collection()
        cursor = collection.find({"premium_end": {"$gt": self.premium_end}})
        users = []
        async for doc in cursor:
            users.append(UserPojo.from_doc(doc))
        return users

    async def find_by_premium_end_before(self) -> list["UserPojo"]:
        collection = await self.get_collection()
        cursor = collection.find({"premium_end": {"$lt": self.premium_end}})
        users = []
        async for doc in cursor:
            users.append(UserPojo.from_doc(doc))
        return users

    @staticmethod
    async def find_all() -> list["UserPojo"]:
        collection = await UserPojo.get_collection()
        cursor = collection.find({})
        users = []
        async for doc in cursor:
            users.append(UserPojo.from_doc(doc))
        return users

    async def find_by_source_ip(self) -> list["UserPojo"]:
        collection = await self.get_collection()
        cursor = collection.find({"source_ip": self.source_ip})
        users = []
        async for doc in cursor:
            users.append(UserPojo.from_doc(doc))
        return users

    async def find_by_last_login_after(self) -> list["UserPojo"]:
        collection = await self.get_collection()
        cursor = collection.find({"last_login": {"$gt": self.last_login}})
        users = []
        async for doc in cursor:
            users.append(UserPojo.from_doc(doc))
        return users

    async def find_by_last_login_before(self) -> list["UserPojo"]:
        collection = await self.get_collection()
        cursor = collection.find({"last_login": {"$lt": self.last_login}})
        users = []
        async for doc in cursor:
            users.append(UserPojo.from_doc(doc))
        return users

    async def find_by_created_after(self) -> list["UserPojo"]:
        collection = await self.get_collection()
        cursor = collection.find({"created_at": {"$gt": self.created_at}})
        users = []
        async for doc in cursor:
            users.append(UserPojo.from_doc(doc))
        return users

    async def find_by_created_before(self) -> list["UserPojo"]:
        collection = await self.get_collection()
        cursor = collection.find({"created_at": {"$lt": self.created_at}})
        users = []
        async for doc in cursor:
            users.append(UserPojo.from_doc(doc))
        return users

    async def update(self) -> bool:
        collection = await self.get_collection()
        result = await collection.update_one(
            {"user_id": self.user_id},
            {"$set": {
                "total_download": self.total_download,
                "total_upload": self.total_upload,
                "source_ip": self.source_ip,
                "last_login": self.last_login,
                "is_premium": self.is_premium,
                "premium_end": self.premium_end,
            }}
        )
        return result.modified_count > 0

    async def insert(self) -> bool:
        collection = await self.get_collection()
        result = await collection.insert_one(self.to_doc())
        return bool(result.inserted_id)

    async def delete(self) -> bool:
        collection = await self.get_collection()
        result = await collection.delete_one({"user_id": self.user_id})
        return result.deleted_count > 0
