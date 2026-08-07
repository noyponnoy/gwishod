import asyncio
import json
import logging

from fastapi import Query as QueryParam, Request
from starlette.responses import PlainTextResponse, JSONResponse

from src.client_3xui_api import client
from src.db.v3.a3xui.server_pojo import ServerPojo
from src.db.v3.a3xui.user_pojo import UserPojo

logger = logging.getLogger(__name__)


async def get_servers():
    servers = await ServerPojo.find_all()
    return PlainTextResponse(
        json.dumps([s.to_doc() for s in servers], default=str),
        status_code=200,
    )


async def get_server(server_ip: str = QueryParam(...)):
    server = ServerPojo()
    server.server_ip = server_ip
    server = await server.find_by_ip()
    return PlainTextResponse(json.dumps(server.to_doc(), default=str), status_code=200)


async def update_server(request: Request):
    body = (await request.body()).decode("utf-8")
    srv = ServerPojo.from_doc(json.loads(body))
    server = ServerPojo()
    server.server_ip = srv.server_ip
    server = await server.find_by_ip()

    server.server_domain_port_path = srv.server_domain_port_path
    server.server_domain_port_path_sub = srv.server_domain_port_path_sub
    server.login = srv.login
    server.password = srv.password
    server.session = srv.session
    server.t_name = srv.t_name
    server.description = srv.description

    await server.update()
    return PlainTextResponse("Server updated", status_code=200)


async def add_server(request: Request):
    body = (await request.body()).decode("utf-8")
    srv = ServerPojo.from_doc(json.loads(body))
    await srv.insert()
    users = await UserPojo.find_all()

    async def _create_users():
        for user in users:
            await client.create_user_from_server(user.tg_id, srv.server_ip)

    asyncio.create_task(_create_users())
    return PlainTextResponse("Server added", status_code=200)


async def delete_server(server_ip: str = QueryParam(...)):
    server = ServerPojo()
    server.server_ip = server_ip
    await server.delete()
    return PlainTextResponse("Server deleted", status_code=200)
