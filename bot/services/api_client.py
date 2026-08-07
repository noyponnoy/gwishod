import httpx
from bot.config import API_BASE_URL


class ApiClient:
    def __init__(self):
        self.base = API_BASE_URL
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get(self, path: str, params: dict = None) -> dict:
        try:
            r = await self.client.get(f"{self.base}{path}", params=params)
            return r.json()
        except Exception as e:
            return {"success": 0, "message": str(e), "data": []}

    async def post(self, path: str, data: dict = None) -> dict:
        try:
            r = await self.client.post(f"{self.base}{path}", data=data)
            return r.json()
        except Exception as e:
            return {"success": 0, "message": str(e), "data": []}


api = ApiClient()
