from typing import List

import httpx

from ..schemas.config import Config


Configs = List[Config]

_HEADERS_KEY = "Hiddify-API-Key"


async def get_all_configs_api(
    url: str, proxy_path: str, api_key: str
) -> Configs:
    request_url = f"{url}/{proxy_path}/api/v2/user/all-configs/"
    async with httpx.AsyncClient() as client:
        response = await client.get(request_url, headers={_HEADERS_KEY: api_key})
        response.raise_for_status()
        return [Config.model_validate(item) for item in response.json()]
