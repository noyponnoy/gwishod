import random
from datetime import datetime, timedelta, timezone
from typing import Optional

import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "otp_codes"


class OtpPojo:
    def __init__(self, **kwargs):
        self.email: str = kwargs.get("email", "")
        self.code: str = kwargs.get("code", "")
        self.created_at: datetime = kwargs.get("created_at", datetime.now(timezone.utc))
        self.expires_at: datetime = kwargs.get(
            "expires_at", datetime.now(timezone.utc) + timedelta(minutes=10)
        )
        self.used: bool = kwargs.get("used", False)

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    @staticmethod
    def generate_code() -> str:
        return str(random.randint(100000, 999999))

    def to_doc(self) -> dict:
        return {
            "email": self.email,
            "code": self.code,
            "createdAt": self.created_at,
            "expiresAt": self.expires_at,
            "used": self.used,
        }

    @staticmethod
    def from_doc(doc: dict) -> "OtpPojo":
        otp = OtpPojo()
        otp.email = doc.get("email", "")
        otp.code = doc.get("code", "")
        otp.created_at = doc.get("createdAt", datetime.now(timezone.utc))
        otp.expires_at = doc.get("expiresAt", datetime.now(timezone.utc))
        otp.used = doc.get("used", False)
        return otp

    async def insert(self) -> bool:
        collection = await self.get_collection()
        await collection.insert_one(self.to_doc())
        return True

    @staticmethod
    async def find_valid(email: str, code: str) -> Optional["OtpPojo"]:
        collection = await OtpPojo.get_collection()
        now = datetime.now(timezone.utc)
        doc = await collection.find_one(
            {"email": email, "code": code, "used": False, "expiresAt": {"$gt": now}},
            sort=[("createdAt", -1)],
        )
        return OtpPojo.from_doc(doc) if doc else None

    async def mark_used(self) -> bool:
        collection = await self.get_collection()
        result = await collection.update_one(
            {"email": self.email, "code": self.code},
            {"$set": {"used": True}},
        )
        return result.modified_count >= 1
