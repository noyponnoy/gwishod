import motor.motor_asyncio

MONGODB_URI = "mongodb://127.0.0.1:27017/?retryWrites=true&w=majority"
DB_NAME = "GreyWebVPN"
COLLECTION_NAME = "tariffs_3xui_v3"


class TariffPojo:
    def __init__(self):
        self.t_name: int = 0
        self.name: str = "0"
        self.description: str = "0"
        self.price: int = 0

    @staticmethod
    async def get_collection():
        client = motor.motor_asyncio.AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        return db[COLLECTION_NAME]

    def to_doc(self) -> dict:
        return {
            "t_name": self.t_name,
            "name": self.name,
            "description": self.description,
            "price": self.price,
        }

    @staticmethod
    def from_doc(doc: dict) -> "TariffPojo":
        t = TariffPojo()
        t.t_name = doc.get("t_name", 0)
        t.name = doc.get("name", "0")
        t.description = doc.get("description", "0")
        t.price = doc.get("price", 0)
        return t

    async def is_exist(self) -> bool:
        collection = await self.get_collection()
        result = await collection.find_one({"t_name": self.t_name})
        return result is not None

    async def insert(self) -> bool:
        collection = await self.get_collection()
        await collection.insert_one(self.to_doc())
        return True

    @staticmethod
    async def find_all() -> list["TariffPojo"]:
        collection = await TariffPojo.get_collection()
        cursor = collection.find({})
        tariffs = []
        async for doc in cursor:
            tariffs.append(TariffPojo.from_doc(doc))
        return tariffs

    async def delete(self) -> bool:
        collection = await self.get_collection()
        await collection.delete_one({"t_name": self.t_name})
        return True

    async def update(self) -> bool:
        collection = await self.get_collection()
        await collection.update_one(
            {"t_name": self.t_name},
            {"$set": {
                "name": self.name,
                "description": self.description,
                "price": self.price,
            }}
        )
        return True

    async def find(self) -> "TariffPojo":
        collection = await self.get_collection()
        doc = await collection.find_one({"name": self.name})
        return TariffPojo.from_doc(doc) if doc else TariffPojo()
