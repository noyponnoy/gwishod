import asyncio
import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from src.db.v3.a3xui.server_pojo import ServerPojo
from src.db.v3.a3xui.user_pojo import UserPojo

logger = logging.getLogger(__name__)

_TIMEOUT_LONG = httpx.Timeout(300.0, read=300.0)
_TIMEOUT_SHORT = httpx.Timeout(5.0, read=3.0)


def _now_ms() -> int:
    """Current UTC time in milliseconds."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


async def login_to_all_servers(tg_id: Optional[str] = None) -> bool:
    need_update_progress = tg_id is not None
    try:
        servers = await ServerPojo.find_all()
    except Exception:
        servers = []

    if not servers:
        logger.error("No servers available for login.")
        return False

    percent_one_server = 100 // len(servers)
    state = {"percent_done": 0}
    all_success = True
    max_concurrent = os.cpu_count() or 4
    semaphore = asyncio.Semaphore(max_concurrent)

    async with httpx.AsyncClient(timeout=_TIMEOUT_LONG) as client:

        async def _process(server):
            async with semaphore:
                url = (
                    f"https://{server.server_domain_port_path}"
                    f"/login?username={server.login}&password={server.password}"
                )
                try:
                    response = await client.post(url)
                except Exception as err:
                    logger.error(
                        "Failed to login to server %s: %s",
                        server.server_domain_port_path, err,
                    )
                    return

                try:
                    result = response.json()
                except Exception as err:
                    logger.error(
                        "Failed to parse login response from %s: %s",
                        server.server_domain_port_path, err,
                    )
                    return

                if not result.get("success"):
                    logger.error(
                        "Login failed for server %s.",
                        server.server_domain_port_path,
                    )
                    return

                cookie_headers = [
                    v
                    for k, v in response.headers.multi_items()
                    if k.lower() == "set-cookie"
                ]
                if not cookie_headers:
                    logger.error(
                        "No cookies received from server %s.",
                        server.server_domain_port_path,
                    )
                    return

                # Prefer second cookie if available, otherwise first
                cookie_raw = (
                    cookie_headers[1]
                    if len(cookie_headers) > 1
                    else cookie_headers[0]
                )
                server.session = cookie_raw.split(";")[0]

                try:
                    if not await server.update():
                        logger.error(
                            "Failed to update session for server %s.",
                            server.server_domain_port_path,
                        )
                except Exception:
                    logger.error(
                        "Failed to update session for server %s.",
                        server.server_domain_port_path,
                    )

                if need_update_progress:
                    state["percent_done"] += percent_one_server
                    progress_url = (
                        f"http://localhost:8080/viewupdateupdater"
                        f"?tg_id={tg_id}&percent={state['percent_done']}%25"
                    )
                    try:
                        await client.get(progress_url)
                    except Exception:
                        logger.error(
                            "Failed to update progress for tg_id: %s", tg_id
                        )

        await asyncio.gather(*[_process(s) for s in servers])

    return all_success


async def create_user(tg_id: str) -> bool:
    user = UserPojo()
    user.tg_id = tg_id

    if await user.is_exist():
        user = await user.find()
        return user.free

    try:
        success = await user.insert()
    except Exception:
        success = False
    if not success:
        logger.error("Failed to create user.\nUser telegram ID: %s", tg_id)
        return False

    user.expired_at = {"1": _now_ms(), "2": _now_ms()}
    user.free = True
    await user.update()

    if not await login_to_all_servers(tg_id):
        logger.error(
            "Failed to login to all servers.\nUser telegram ID: %s", tg_id
        )
        return False

    try:
        servers = await ServerPojo.find_all()
    except Exception as err:
        logger.error("Failed to fetch servers: %s", err)
        servers = []

    if not servers:
        logger.error("No servers available.\nUser telegram ID: %s", tg_id)
        return False

    percent_one_server = 100 // len(servers)
    state = {"percent_done": 0}
    all_success = True
    max_concurrent = os.cpu_count() or 4
    semaphore = asyncio.Semaphore(max_concurrent)

    async with httpx.AsyncClient(timeout=_TIMEOUT_LONG) as client:

        async def _process(idx, server):
            async with semaphore:
                url = f"https://{server.server_domain_port_path}/panel/api/inbounds/list"
                try:
                    response = await client.get(
                        url, headers={"Cookie": server.session}
                    )
                except Exception as err:
                    logger.error(
                        "Failed to fetch inbounds from %s: %s",
                        server.server_domain_port_path, err,
                    )
                    return

                try:
                    result = response.json()
                except Exception as err:
                    logger.error(
                        "Failed to parse response from %s: %s",
                        server.server_domain_port_path, err,
                    )
                    return

                if not result.get("success"):
                    logger.error(
                        "Failed to read inbounds from %s.\nUser telegram ID: %s",
                        server.server_domain_port_path, tg_id,
                    )
                    return

                inbounds = result.get("obj", [])
                if not isinstance(inbounds, list):
                    inbounds = []

                for item in inbounds:
                    inbound_id = item.get("id", 0)
                    port = item.get("port", 0)
                    client_data = {
                        "clients": [
                            {
                                "id": user.uuid,
                                "alterId": 0,
                                "email": f"{user.tg_id}-{port}",
                                "limitIp": 2,
                                "totalGB": 0,
                                "expiryTime": "0",
                                "enable": False,
                                "tgId": user.tg_id,
                                "subId": str(user.tg_id),
                                "flow": "xtls-rprx-vision",
                            }
                        ]
                    }
                    cur = {
                        "id": inbound_id,
                        "settings": json.dumps(client_data),
                    }
                    update_url = (
                        f"https://{server.server_domain_port_path}"
                        f"/panel/api/inbounds/addClient"
                    )
                    try:
                        update_resp = await client.post(
                            update_url,
                            headers={
                                "Cookie": server.session,
                                "Content-Type": "application/json",
                            },
                            content=json.dumps(cur),
                        )
                        update_result = update_resp.json()
                        if not update_result.get("success"):
                            logger.error(
                                "Failed to add client to inbound %s on %s.\n"
                                "User telegram ID: %s",
                                inbound_id,
                                server.server_domain_port_path,
                                tg_id,
                            )
                    except Exception as err:
                        logger.error(
                            "Failed to update inbound %s: %s", inbound_id, err
                        )

                state["percent_done"] += percent_one_server
                progress_url = (
                    f"http://localhost:8080/viewcreateupdater"
                    f"?tg_id={tg_id}&percent={state['percent_done']}%25"
                )
                try:
                    await client.get(progress_url)
                except Exception:
                    logger.error(
                        "Failed to update progress for tg_id: %s", tg_id
                    )

        await asyncio.gather(
            *[_process(i, s) for i, s in enumerate(servers)]
        )

    user.litenotif0 = False
    user.pronotif0 = True
    try:
        await user.update()
    except Exception as err:
        logger.error(
            "Failed to update user after creation: %s\nUser telegram ID: %s",
            err,
            tg_id,
        )

    return all_success


async def create_free_access(tg_id: str) -> bool:
    user = UserPojo()
    user.tg_id = tg_id

    try:
        user = await user.find()
    except Exception as err:
        logger.error("Failed to find user: %s", err)
        return False

    if not await user.is_exist():
        logger.error("User does not exist: %s", tg_id)
        return False

    if not user.free:
        return False

    now = _now_ms()
    user.expired_at = {
        "1": now + 259_200_000,  # 3 days
        "2": now,
    }
    user.free = False

    try:
        await user.update()
    except Exception as err:
        logger.error("Failed to update user: %s", err)
        return False

    if not await login_to_all_servers(None):
        logger.error("Failed to login to all servers.")
        return False

    try:
        servers = await ServerPojo.find_all()
    except Exception as err:
        logger.error("Failed to fetch servers: %s", err)
        return False

    success = True
    max_concurrent = os.cpu_count() or 4
    semaphore = asyncio.Semaphore(max_concurrent)

    async with httpx.AsyncClient(timeout=_TIMEOUT_LONG) as client:

        async def _process(server):
            async with semaphore:
                if server.t_name != 1:
                    return

                url = f"https://{server.server_domain_port_path}/panel/api/inbounds/list"
                try:
                    response = await client.get(
                        url, headers={"Cookie": server.session}
                    )
                except Exception as err:
                    logger.error("Failed to fetch inbounds: %s", err)
                    return

                try:
                    result = response.json()
                except Exception as err:
                    logger.error("Failed to parse response: %s", err)
                    return

                if not result.get("success"):
                    logger.error(
                        "Failed to fetch inbounds from server: %s",
                        server.server_domain_port_path,
                    )
                    return

                inbounds = result.get("obj", [])
                if not isinstance(inbounds, list):
                    logger.error("Failed to parse inbounds")
                    return

                for item in inbounds:
                    inbound_id = item.get("id", 0)
                    port = item.get("port", 0)
                    client_data = {
                        "clients": [
                            {
                                "id": user.uuid,
                                "alterId": 0,
                                "email": f"{user.tg_id}-{port}",
                                "limitIp": 2,
                                "totalGB": 0,
                                "expiryTime": "0",
                                "enable": True,
                                "tgId": user.tg_id,
                                "subId": str(user.tg_id),
                                "flow": "xtls-rprx-vision",
                            }
                        ]
                    }
                    cur = {
                        "id": inbound_id,
                        "settings": json.dumps(client_data),
                    }
                    update_url = (
                        f"https://{server.server_domain_port_path}"
                        f"/panel/api/inbounds/updateClient/{user.uuid}"
                    )
                    try:
                        update_resp = await client.post(
                            update_url,
                            headers={
                                "Cookie": server.session,
                                "Content-Type": "application/json",
                            },
                            content=json.dumps(cur),
                        )
                    except Exception as err:
                        logger.error("Failed to update client: %s", err)
                        return

                    try:
                        update_result = update_resp.json()
                    except Exception as err:
                        logger.error(
                            "Failed to parse update response: %s", err
                        )
                        return

                    if not update_result.get("success"):
                        logger.error(
                            "Failed to update inbound for user: %s",
                            user.tg_id,
                        )
                        return

        await asyncio.gather(*[_process(s) for s in servers])

    return success


async def create_user_from_server(tg_id: str, server_ip: str) -> bool:
    user = UserPojo()
    user.tg_id = tg_id
    try:
        user = await user.find()
    except Exception:
        logger.error("Failed to find user with tg_id: %s", tg_id)
        user = UserPojo()

    if not await login_to_all_servers(None):
        logger.error("Failed to login to all servers.")
        return False

    server = ServerPojo()
    server.server_ip = server_ip
    try:
        server = await server.find_by_ip()
    except Exception:
        logger.error("Failed to find server with IP: %s", server_ip)
        server = ServerPojo()

    async with httpx.AsyncClient(timeout=_TIMEOUT_LONG) as client:
        url = f"https://{server.server_domain_port_path}/panel/api/inbounds/list"
        try:
            response = await client.get(
                url, headers={"Cookie": server.session}
            )
        except Exception as err:
            logger.error("Failed to fetch inbounds list: %s", err)
            return False

        try:
            result = response.json()
        except Exception as err:
            logger.error("Failed to parse response: %s", err)
            return False

        if not result.get("success"):
            logger.error("Server returned failure: %s", result)
            return False

        obj = result.get("obj", [])
        if not isinstance(obj, list):
            logger.error("Failed to parse response object")
            return False

        success = True
        for item in obj:
            inbound_id = item.get("id", 0)
            port = item.get("port", 0)
            expired_at_val = user.expired_at.get(str(server.t_name), 0)
            enable = expired_at_val > _now_ms()

            client_data = {
                "clients": [
                    {
                        "id": user.uuid,
                        "alterId": 0,
                        "email": f"{user.tg_id}-{port}",
                        "limitIp": 2,
                        "totalGB": 0,
                        "expiryTime": "0",
                        "enable": enable,
                        "tgId": user.tg_id,
                        "subId": str(user.tg_id),
                        "flow": "xtls-rprx-vision",
                    }
                ]
            }
            cur = {
                "id": inbound_id,
                "settings": json.dumps(client_data),
            }
            add_url = (
                f"https://{server.server_domain_port_path}"
                f"/panel/api/inbounds/addClient"
            )
            try:
                add_resp = await client.post(
                    add_url,
                    headers={
                        "Cookie": server.session,
                        "Content-Type": "application/json",
                    },
                    content=json.dumps(cur),
                )
            except Exception as err:
                logger.error("Failed to add client: %s", err)
                success = False
                continue

            try:
                add_result = add_resp.json()
            except Exception as err:
                logger.error(
                    "Failed to parse add client response: %s", err
                )
                success = False
                continue

            if not add_result.get("success"):
                logger.error(
                    "Failed to create user inbound: %s, User ID: %s, "
                    "Server: %s, Inbound ID: %s",
                    add_result,
                    user.tg_id,
                    server.server_domain_port_path,
                    inbound_id,
                )
                success = False

    return success


async def update_user_payment(
    tg_id: str, t_name: int, hour: Optional[int] = None
) -> bool:
    if hour is not None:
        hour = hour // 10

    user = UserPojo()
    user.tg_id = tg_id

    if await user.is_exist():
        user = await user.find()

        if t_name == 1:
            user.litenotif0 = False
            user.litenotif1 = False
            user.litenotif2 = False
            user.litenotif3 = False
        if t_name == 2:
            user.pronotif0 = False
            user.pronotif1 = False
            user.pronotif2 = False
            user.pronotif3 = False

        now = _now_ms()

        if hour is None:
            current_exp = user.expired_at.get(str(t_name), 0)
            if current_exp >= now:
                d = user.expired_at.get(str(t_name), 0)
                if t_name == 3:
                    user.expired_at["1"] = d + 7_776_000_000
                elif t_name == 4:
                    user.expired_at["2"] = d + 7_776_000_000
                else:
                    user.expired_at[str(t_name)] = d + 2_592_000_000
            else:
                if t_name == 3:
                    user.expired_at["1"] = now + 7_776_000_000
                elif t_name == 4:
                    user.expired_at["2"] = now + 7_776_000_000
                else:
                    user.expired_at[str(t_name)] = now + 2_592_000_000
        else:
            for i in range(1, 4):  # 1, 2, 3
                current_exp = user.expired_at.get(str(i), 0)
                if current_exp >= now:
                    user.expired_at[str(i)] = (
                        current_exp + hour * 3_600_000
                    )
                else:
                    user.expired_at[str(i)] = now + hour * 3_600_000

        await user.update()

        if await login_to_all_servers(None):
            servers = await ServerPojo.find_all()
            ok = True

            async with httpx.AsyncClient(timeout=_TIMEOUT_SHORT) as client:

                async def _process_server(server):
                    nonlocal ok
                    if server.t_name != t_name and hour is None:
                        return

                    url = (
                        f"https://{server.server_domain_port_path}"
                        f"/panel/api/inbounds/list"
                    )
                    try:
                        response = await client.get(
                            url, headers={"Cookie": server.session}
                        )
                    except Exception as err:
                        logger.error("Request failed: %s", err)
                        ok = False
                        return

                    try:
                        result = response.json()
                    except Exception:
                        ok = False
                        return

                    if not result.get("success"):
                        logger.error(
                            "Failed to update user inbound.\n"
                            "User telegram ID: %s\nServer IP: %s",
                            user.tg_id,
                            server.server_domain_port_path,
                        )
                        ok = False
                        return

                    inbounds = result.get("obj", [])
                    if not isinstance(inbounds, list):
                        inbounds = []

                    for item in inbounds:
                        inbound_id = item.get("id", 0)
                        port = item.get("port", 0)
                        expired_at = user.expired_at.get(
                            str(server.t_name), 0
                        )
                        now_check = _now_ms()
                        enable = expired_at > now_check

                        client_data = {
                            "clients": [
                                {
                                    "id": user.uuid,
                                    "alterId": 0,
                                    "email": f"{user.tg_id}-{port}",
                                    "limitIp": 2,
                                    "totalGB": 0,
                                    "expiryTime": 0,
                                    "enable": enable,
                                    "tgId": user.tg_id,
                                    "subId": str(user.tg_id),
                                    "flow": "xtls-rprx-vision",
                                }
                            ]
                        }
                        cur = {
                            "id": inbound_id,
                            "settings": json.dumps(client_data),
                        }
                        update_url = (
                            f"https://{server.server_domain_port_path}"
                            f"/panel/api/inbounds/updateClient/{user.uuid}"
                        )
                        try:
                            update_resp = await client.post(
                                update_url,
                                headers={
                                    "Cookie": server.session,
                                    "Content-Type": "application/json",
                                },
                                content=json.dumps(cur),
                            )
                        except Exception as err:
                            logger.error("%s", err)
                            ok = False
                            continue

                        try:
                            update_result = update_resp.json()
                        except Exception:
                            ok = False
                            continue

                        if not update_result.get("success"):
                            logger.error(
                                "Failed to update user inbound.\n"
                                "User telegram ID: %s\n"
                                "Server IP: %s\nInbound ID: %s",
                                user.tg_id,
                                server.server_domain_port_path,
                                inbound_id,
                            )
                            ok = False
                        else:
                            user.enable[str(server.t_name)] = True
                            await user.update()

                tasks = [
                    asyncio.create_task(_process_server(s)) for s in servers
                ]
                await asyncio.gather(*tasks)

            async with httpx.AsyncClient(timeout=_TIMEOUT_SHORT) as notify_client:
                try:
                    await notify_client.get(
                        f"http://localhost:8080/profile/success/pay"
                        f"?tg_id={user.tg_id}",
                        headers={"Content-Type": "application/json"},
                    )
                except Exception as err:
                    logger.error("Failed to get response: %s", err)

            return True
        else:
            logger.error(
                "Failed to login to all servers when updating user.\n"
                "User telegram ID: %s",
                user.tg_id,
            )
            return False
    else:
        logger.error(
            "Failed to update user.\nUser telegram ID: %s", user.tg_id
        )
        await create_user(user.tg_id)
        return False


async def get_user_subscription(tg_id: str) -> str:
    user = UserPojo()
    user.tg_id = tg_id

    if not await user.is_exist():
        return ""

    if not await login_to_all_servers(None):
        return ""

    user = await user.find()
    lite = user.expired_at.get("1", 0)
    pro = user.expired_at.get("2", 0)
    now_timestamp = _now_ms()
    exp_timestamp = 0
    t_name = 0

    if lite > now_timestamp or pro > now_timestamp:
        if lite > pro:
            exp_timestamp = (lite - now_timestamp) // 1000 // 60 // 60 // 24
        if pro >= lite:
            exp_timestamp = (pro - now_timestamp) // 1000 // 60 // 60 // 24

        if pro > now_timestamp:
            t_name = 2
        elif lite > now_timestamp:
            t_name = 1

    exp = f" | {exp_timestamp}D"
    sub_container = ["#profile-update-interval: 1\n"]
    sub_lock = asyncio.Lock()
    servers = await ServerPojo.find_all()

    async with httpx.AsyncClient(timeout=_TIMEOUT_SHORT) as client:

        async def _process(server):
            if server.t_name <= t_name:
                try:
                    response = await client.get(
                        f"https://{server.server_domain_port_path_sub}"
                        f"/{user.tg_id}",
                        headers={"Cookie": server.session},
                    )
                except Exception as err:
                    logger.error("User subscription: %s", err)
                    return

                result_text = response.text
                results = result_text.split("\n")

                async with sub_lock:
                    for line in results:
                        if line.startswith("vmess://"):
                            tmp = line.replace("vmess://", "")
                            tmp = base64.b64decode(tmp).decode("utf-8")
                            tmp = tmp.replace(
                                "@desc@",
                                server.description.replace("@time@", exp),
                            )
                            tmp = base64.b64encode(
                                tmp.encode("utf-8")
                            ).decode("utf-8")
                            sub_container[0] += f"\nvmess://{tmp}"
                        else:
                            sub_container[0] += "\n{}".format(
                                line.replace(
                                    "@desc@",
                                    server.description.replace(
                                        "@time@", exp
                                    ),
                                )
                            )

        tasks = [asyncio.create_task(_process(s)) for s in servers]
        await asyncio.gather(*tasks)

    sub = sub_container[0].replace("\n\n", "\n")
    if sub.startswith("\n\n"):
        sub = sub[2:]
    if sub.startswith("\n"):
        sub = sub[1:]
    if sub.endswith("\n"):
        sub = sub[:-1]
    if sub.endswith("\n\n"):
        sub = sub[:-2]
    return sub


async def get_user_exps(tg_id: str) -> str:
    user = UserPojo()
    user.tg_id = tg_id

    if not await user.is_exist():
        logger.error(
            "Failed to update user.\nUser telegram ID: %s", user.tg_id
        )
        return ""

    user = await user.find()
    lite = user.expired_at.get("1", 0)
    pro = user.expired_at.get("2", 0)

    if not await login_to_all_servers(tg_id):
        logger.error(
            "Failed to login to all servers when updating user.\n"
            "User telegram ID: %s",
            user.tg_id,
        )
        return ""

    servers = await ServerPojo.find_all()
    expss = []
    percent_one_server = 100 // len(servers) if servers else 0
    percent_done = 0

    async with httpx.AsyncClient(timeout=_TIMEOUT_SHORT) as client:
        for server in servers:
            url = (
                f"https://{server.server_domain_port_path}"
                f"/panel/api/inbounds/list"
            )
            try:
                response = await client.get(
                    url, headers={"Cookie": server.session}
                )
            except Exception as err:
                logger.error("%s", err)
                percent_done += percent_one_server
                try:
                    await client.get(
                        f"http://localhost:8080/viewupdateupdater"
                        f"?tg_id={tg_id}&percent={percent_done}%25",
                        headers={"Content-Type": "application/json"},
                    )
                except Exception as perr:
                    logger.error("viewupdateupdater: %s", perr)
                continue

            try:
                result = response.json()
            except Exception:
                percent_done += percent_one_server
                try:
                    await client.get(
                        f"http://localhost:8080/viewupdateupdater"
                        f"?tg_id={tg_id}&percent={percent_done}%25",
                        headers={"Content-Type": "application/json"},
                    )
                except Exception as perr:
                    logger.error("viewupdateupdater: %s", perr)
                continue

            if result.get("success"):
                timestamp_ms = 0
                if server.t_name == 1:
                    timestamp_ms = lite
                if server.t_name == 2:
                    timestamp_ms = pro

                dt = datetime.fromtimestamp(
                    timestamp_ms / 1000, tz=timezone.utc
                )
                datetime_str = dt.strftime("%d-%m-%Y")
                now_utc = datetime.now(timezone.utc)

                if dt >= now_utc:
                    expss.append(
                        {"server": server.description, "exp": datetime_str}
                    )

            percent_done += percent_one_server
            try:
                progress_resp = await client.get(
                    f"http://localhost:8080/viewupdateupdater"
                    f"?tg_id={tg_id}&percent={percent_done}%25",
                    headers={"Content-Type": "application/json"},
                )
                logger.debug("%s", progress_resp.text)
            except Exception as err:
                logger.error("viewupdateupdater: %s", err)

    return json.dumps(expss)


async def unload_user_premium(tg_id: str, t_name: int) -> bool:
    servers = await ServerPojo.find_all()
    user = UserPojo()
    user.tg_id = tg_id
    user = await user.find()

    async with httpx.AsyncClient(timeout=_TIMEOUT_LONG) as client:
        for server in servers:
            if server.t_name == t_name:
                url = (
                    f"https://{server.server_domain_port_path}"
                    f"/panel/api/inbounds/list"
                )
                try:
                    response = await client.get(
                        url, headers={"Cookie": server.session}
                    )
                except Exception as err:
                    logger.error("%s", err)
                    continue

                try:
                    result = response.json()
                except Exception:
                    continue

                if result.get("success"):
                    inbounds = result.get("obj", [])
                    if not isinstance(inbounds, list):
                        continue

                    for item in inbounds:
                        inbound_id = item.get("id", 0)
                        port = item.get("port", 0)
                        # No flow field in unload_user_premium
                        client_data = {
                            "clients": [
                                {
                                    "id": user.uuid,
                                    "alterId": 0,
                                    "email": f"{user.tg_id}-{port}",
                                    "limitIp": 2,
                                    "totalGB": 0,
                                    "expiryTime": 0,
                                    "enable": False,
                                    "tgId": user.tg_id,
                                    "subId": str(user.tg_id),
                                }
                            ]
                        }
                        cur = {
                            "id": inbound_id,
                            "settings": json.dumps(client_data),
                        }
                        update_url = (
                            f"https://{server.server_domain_port_path}"
                            f"/panel/api/inbounds/updateClient/{user.uuid}"
                        )
                        try:
                            update_resp = await client.post(
                                update_url,
                                headers={
                                    "Cookie": server.session,
                                    "Content-Type": "application/json",
                                },
                                content=json.dumps(cur),
                            )
                        except Exception as err:
                            logger.error("%s", err)
                            continue

                        try:
                            update_result = update_resp.json()
                        except Exception:
                            continue

                        if not update_result.get("success"):
                            logger.error(
                                "Failed to update user inbound.\n"
                                "User telegram ID: %s\n"
                                "Server IP: %s\nInbound ID: %s",
                                user.tg_id,
                                server.server_domain_port_path,
                                inbound_id,
                            )
                            return False
    return True


async def delete_user(tg_id: str) -> bool:
    servers = await ServerPojo.find_all()
    user = UserPojo()
    user.tg_id = tg_id
    user = await user.find()

    async with httpx.AsyncClient(timeout=_TIMEOUT_LONG) as client:
        for server in servers:
            url = (
                f"https://{server.server_domain_port_path}"
                f"/panel/api/inbounds/list"
            )
            try:
                response = await client.get(
                    url, headers={"Cookie": server.session}
                )
            except Exception as err:
                logger.error("%s", err)
                continue

            try:
                result = response.json()
            except Exception:
                continue

            if result.get("success"):
                inbounds = result.get("obj", [])
                if not isinstance(inbounds, list):
                    continue

                for item in inbounds:
                    inbound_id = item.get("id", 0)
                    del_url = (
                        f"https://{server.server_domain_port_path}"
                        f"/panel/api/inbounds/{inbound_id}"
                        f"/delClient/{user.uuid}"
                    )
                    try:
                        del_resp = await client.post(
                            del_url,
                            headers={
                                "Cookie": server.session,
                                "Content-Type": "application/json",
                            },
                        )
                    except Exception as err:
                        logger.error("%s", err)
                        continue

                    try:
                        del_result = del_resp.json()
                    except Exception:
                        continue

                    if not del_result.get("success"):
                        logger.error("%s", del_result.get("msg", ""))
                        return False
    return True


async def recreate_user() -> bool:
    servers = await ServerPojo.find_all()
    servers_config: dict = {}

    async with httpx.AsyncClient(timeout=_TIMEOUT_SHORT) as client:
        for server in servers:
            url = (
                f"https://{server.server_domain_port_path}"
                f"/panel/api/inbounds/list"
            )
            try:
                response = await client.get(
                    url, headers={"Cookie": server.session}
                )
            except Exception as err:
                logger.error("%s", err)
                continue

            try:
                result = response.json()
            except Exception:
                continue

            if result.get("success"):
                servers_config[server.server_ip] = result

    users = await UserPojo.find_all()

    for server in servers:
        for user in users:
            result = servers_config.get(server.server_ip)
            if result is None:
                continue

            obj = result.get("obj", [])
            if not isinstance(obj, list):
                continue

            for item in obj:
                client_stats = item.get("clientStats", [])
                need_to_recreate = True
                for client_stat in client_stats:
                    if client_stat.get("email") == f"{user.tg_id}-443":
                        need_to_recreate = False
                        break

                if need_to_recreate:
                    await create_user_from_server(
                        user.tg_id, server.server_ip
                    )

    return True


async def upd():
    users = await UserPojo.find_all()
    servers = await ServerPojo.find_all()

    now = _now_ms()
    u1 = [u for u in users if u.expired_at.get("1", 0) > now]
    u2 = [u for u in users if u.expired_at.get("2", 0) > now]

    async with httpx.AsyncClient(timeout=_TIMEOUT_LONG) as client:
        for server in servers:
            if server.t_name == 1:
                url = (
                    f"https://{server.server_domain_port_path}"
                    f"/panel/api/inbounds/list"
                )
                try:
                    response = await client.get(
                        url, headers={"Cookie": server.session}
                    )
                except Exception:
                    continue

                try:
                    result = response.json()
                except Exception:
                    continue

                if result.get("success"):
                    inbounds = result.get("obj", [])
                    if not isinstance(inbounds, list):
                        continue

                    for item in inbounds:
                        inbound_id = item.get("id", 0)
                        port = item.get("port", 0)

                        for u11 in u1:
                            expired_at_1 = u11.expired_at.get("1", 0)
                            enable = expired_at_1 > _now_ms()
                            # No flow field in upd
                            client_data = {
                                "clients": [
                                    {
                                        "id": u11.uuid,
                                        "alterId": 0,
                                        "email": f"{u11.tg_id}-{port}",
                                        "limitIp": 2,
                                        "totalGB": 0,
                                        "expiryTime": 0,
                                        "enable": enable,
                                        "tgId": u11.tg_id,
                                        "subId": str(u11.tg_id),
                                    }
                                ]
                            }
                            cur = {
                                "id": inbound_id,
                                "settings": json.dumps(client_data),
                            }
                            update_url = (
                                f"https://{server.server_domain_port_path}"
                                f"/panel/api/inbounds/updateClient"
                                f"/{u11.uuid}"
                            )
                            try:
                                update_resp = await client.post(
                                    update_url,
                                    headers={
                                        "Cookie": server.session,
                                        "Content-Type": "application/json",
                                    },
                                    content=json.dumps(cur),
                                )
                                update_result = update_resp.json()
                                if not update_result.get("success"):
                                    logger.error(
                                        "Failed to update user inbound.\n"
                                        "User telegram ID: %s\n"
                                        "Server IP: %s\n"
                                        "Inbound ID: %s",
                                        u11.tg_id,
                                        server.server_domain_port_path,
                                        inbound_id,
                                    )
                                else:
                                    u11.enable["1"] = True
                                    await u11.update()
                            except Exception:
                                logger.error(
                                    "Failed to update user inbound.\n"
                                    "User telegram ID: %s\n"
                                    "Server IP: %s\n"
                                    "Inbound ID: %s",
                                    u11.tg_id,
                                    server.server_domain_port_path,
                                    inbound_id,
                                )

            if server.t_name == 2:
                url = (
                    f"https://{server.server_domain_port_path}"
                    f"/panel/api/inbounds/list"
                )
                try:
                    response = await client.get(
                        url, headers={"Cookie": server.session}
                    )
                except Exception:
                    continue

                try:
                    result = response.json()
                except Exception:
                    continue

                if result.get("success"):
                    inbounds = result.get("obj", [])
                    if not isinstance(inbounds, list):
                        continue

                    for item in inbounds:
                        inbound_id = item.get("id", 0)
                        port = item.get("port", 0)

                        for u22 in u2:
                            expired_at_2 = u22.expired_at.get("2", 0)
                            enable = expired_at_2 > _now_ms()
                            # No flow field in upd
                            client_data = {
                                "clients": [
                                    {
                                        "id": u22.uuid,
                                        "alterId": 0,
                                        "email": f"{u22.tg_id}-{port}",
                                        "limitIp": 2,
                                        "totalGB": 0,
                                        "expiryTime": 0,
                                        "enable": enable,
                                        "tgId": u22.tg_id,
                                        "subId": str(u22.tg_id),
                                    }
                                ]
                            }
                            cur = {
                                "id": inbound_id,
                                "settings": json.dumps(client_data),
                            }
                            update_url = (
                                f"https://{server.server_domain_port_path}"
                                f"/panel/api/inbounds/updateClient"
                                f"/{u22.uuid}"
                            )
                            try:
                                update_resp = await client.post(
                                    update_url,
                                    headers={
                                        "Cookie": server.session,
                                        "Content-Type": "application/json",
                                    },
                                    content=json.dumps(cur),
                                )
                                update_result = update_resp.json()
                                if not update_result.get("success"):
                                    logger.error(
                                        "Failed to update user inbound.\n"
                                        "User telegram ID: %s\n"
                                        "Server IP: %s\n"
                                        "Inbound ID: %s",
                                        u22.tg_id,
                                        server.server_domain_port_path,
                                        inbound_id,
                                    )
                                else:
                                    u22.enable["2"] = True
                                    await u22.update()
                            except Exception:
                                logger.error(
                                    "Failed to update user inbound.\n"
                                    "User telegram ID: %s\n"
                                    "Server IP: %s\n"
                                    "Inbound ID: %s",
                                    u22.tg_id,
                                    server.server_domain_port_path,
                                    inbound_id,
                                )
