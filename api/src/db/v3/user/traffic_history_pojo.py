import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "traffic_v3"


class TrafficHistory:
    def __init__(self):
        self.user_id: str = ""
        self.upload: int = 0
        self.download: int = 0
        self.date: int = 0

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "user_id": self.user_id,
            "upload": self.upload,
            "download": self.download,
            "date": self.date,
        }

    @staticmethod
    def from_doc(doc: dict) -> "TrafficHistory":
        t = TrafficHistory()
        t.user_id = doc.get("user_id", "")
        t.upload = doc.get("upload", 0)
        t.download = doc.get("download", 0)
        t.date = doc.get("date", 0)
        return t

    async def is_exist(self) -> bool:
        collection = await self.get_collection()
        result = await collection.find_one({"user_id": self.user_id})
        return result is not None

    async def insert(self) -> bool:
        collection = await self.get_collection()
        result = await collection.insert_one(self.to_doc())
        return bool(result.inserted_id)

    async def find_by_user_id(self) -> list["TrafficHistory"]:
        collection = await self.get_collection()
        cursor = collection.find({"user_id": self.user_id})
        results = []
        async for doc in cursor:
            results.append(TrafficHistory.from_doc(doc))
        return results

    @staticmethod
    async def find_all() -> list["TrafficHistory"]:
        collection = await TrafficHistory.get_collection()
        cursor = collection.find({})
        results = []
        async for doc in cursor:
            results.append(TrafficHistory.from_doc(doc))
        return results
