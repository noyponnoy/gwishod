from typing import List

import httpx

from ..schemas.admin import Admin
from ..schemas.patch_admin import PatchAdmin
from ..schemas.patch_user import PatchUser
from ..schemas.server_status_output import ServerStatusOutput
from ..schemas.successful import Successful
from ..schemas.user import User


Admins = List[Admin]
Users = List[User]

_HEADERS_KEY = "Hiddify-API-Key"


def _admin_url(url: str, proxy_path: str, endpoint: str) -> str:
    return f"{url}/{proxy_path}/api/v2/admin/{endpoint}/"


async def get_all_admins(url: str, proxy_path: str, api_key: str) -> Admins:
    request_url = _admin_url(url, proxy_path, "admin_user")
    async with httpx.AsyncClient() as client:
        response = await client.get(request_url, headers={_HEADERS_KEY: api_key})
        response.raise_for_status()
        return [Admin.model_validate(item) for item in response.json()]


async def create_an_admin(
    url: str, proxy_path: str, api_key: str, admin: Admin
) -> Admin:
    request_url = _admin_url(url, proxy_path, "admin_user")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            request_url,
            headers={_HEADERS_KEY: api_key},
            json=admin.model_dump(by_alias=True),
        )
        response.raise_for_status()
        return Admin.model_validate(response.json())


async def delete_an_admin(
    url: str, proxy_path: str, api_key: str, admin_uuid: str
) -> Successful:
    request_url = f"{_admin_url(url, proxy_path, 'admin_user')}{admin_uuid}/"
    async with httpx.AsyncClient() as client:
        response = await client.delete(request_url, headers={_HEADERS_KEY: api_key})
        response.raise_for_status()
        return Successful.model_validate(response.json())


async def get_an_admin(
    url: str, proxy_path: str, api_key: str, admin_uuid: str
) -> Admin:
    request_url = f"{_admin_url(url, proxy_path, 'admin_user')}{admin_uuid}/"
    async with httpx.AsyncClient() as client:
        response = await client.get(request_url, headers={_HEADERS_KEY: api_key})
        response.raise_for_status()
        return Admin.model_validate(response.json())


async def update_an_admin(
    url: str, proxy_path: str, api_key: str, admin_uuid: str, admin: Admin
) -> PatchAdmin:
    request_url = f"{_admin_url(url, proxy_path, 'admin_user')}{admin_uuid}/"
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            request_url,
            headers={_HEADERS_KEY: api_key},
            json=admin.model_dump(by_alias=True),
        )
        response.raise_for_status()
        return PatchAdmin.model_validate(response.json())


async def get_server_status(
    url: str, proxy_path: str, api_key: str
) -> ServerStatusOutput:
    request_url = _admin_url(url, proxy_path, "server_status")
    async with httpx.AsyncClient() as client:
        response = await client.get(request_url, headers={_HEADERS_KEY: api_key})
        response.raise_for_status()
        return ServerStatusOutput.model_validate(response.json())


async def list_users_of_current_admin(
    url: str, proxy_path: str, api_key: str
) -> Users:
    request_url = _admin_url(url, proxy_path, "user")
    async with httpx.AsyncClient() as client:
        response = await client.get(request_url, headers={_HEADERS_KEY: api_key})
        response.raise_for_status()
        return [User.model_validate(item) for item in response.json()]


async def create_a_user(
    url: str, proxy_path: str, api_key: str, user: User
) -> User:
    request_url = _admin_url(url, proxy_path, "user")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            request_url,
            headers={_HEADERS_KEY: api_key},
            json=user.model_dump(by_alias=True),
        )
        response.raise_for_status()
        return User.model_validate(response.json())


async def delete_a_user(
    url: str, proxy_path: str, api_key: str, user_uuid: str
) -> Successful:
    request_url = f"{_admin_url(url, proxy_path, 'user')}{user_uuid}/"
    async with httpx.AsyncClient() as client:
        response = await client.delete(request_url, headers={_HEADERS_KEY: api_key})
        response.raise_for_status()
        return Successful.model_validate(response.json())


async def get_details_of_a_user(
    url: str, proxy_path: str, api_key: str, user_uuid: str
) -> User:
    request_url = f"{_admin_url(url, proxy_path, 'user')}{user_uuid}/"
    async with httpx.AsyncClient() as client:
        response = await client.get(request_url, headers={_HEADERS_KEY: api_key})
        response.raise_for_status()
        return User.model_validate(response.json())


async def update_a_user(
    url: str, proxy_path: str, api_key: str, user_uuid: str, user: User
) -> PatchUser:
    request_url = f"{_admin_url(url, proxy_path, 'user')}{user_uuid}/"
    async with httpx.AsyncClient() as client:
        response = await client.patch(
            request_url,
            headers={_HEADERS_KEY: api_key},
            json=user.model_dump(by_alias=True),
        )
        response.raise_for_status()
        return PatchUser.model_validate(response.json())
