import logging

from fastapi import Query as QueryParam, Request
from starlette.responses import JSONResponse

from src.db.v3.admin.admin_pojo import AdminPojo
from src.db.v3.code.code_pojo import CodePojo
from src.db.v3.payments.tariff_pojo import TariffPojo
from src.db.v3.servers.server_pojo import ServerPojo
from src.db.v3.user.traffic_history_pojo import TrafficHistory
from src.db.v3.user.user_pojo import UserPojo
from src.endpoints.response_object import ResponseJson, ResponseJsonMessage

logger = logging.getLogger(__name__)


async def _check_admin_token(request: Request):
    """Helper: validate admin token from Authorization header."""
    admin_user = AdminPojo()
    admin_user.token = request.headers.get("Authorization", "")
    admin_user = await admin_user.find_by_token()
    if not admin_user or not admin_user.login:
        return None, JSONResponse(
            status_code=401,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=401, info="Unauthorized"),
                data={},
            ).to_dict(),
        )
    if not await admin_user.check_token():
        return None, JSONResponse(
            status_code=401,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=401, info="Token expired"),
                data={},
            ).to_dict(),
        )
    return admin_user, None


async def get_premium_users(request: Request):
    admin_user, err = await _check_admin_token(request)
    if err:
        return err
    user_p = UserPojo()
    user_p.is_premium = True
    users = await UserPojo.find_by_premium(user_p)
    return JSONResponse(
        status_code=200,
        content=ResponseJson(
            success=True,
            message=ResponseJsonMessage(status_code=200, info="Premium users"),
            data=[u.to_doc() for u in users],
        ).to_dict(),
    )


async def get_not_premium_users(request: Request):
    admin_user, err = await _check_admin_token(request)
    if err:
        return err
    user_p = UserPojo()
    user_p.is_premium = False
    users = await UserPojo.find_by_premium(user_p)
    return JSONResponse(
        status_code=200,
        content=ResponseJson(
            success=True,
            message=ResponseJsonMessage(status_code=200, info="Not premium users"),
            data=[u.to_doc() for u in users],
        ).to_dict(),
    )


async def get_all_users(request: Request):
    admin_user, err = await _check_admin_token(request)
    if err:
        return err
    users = await UserPojo.find_all()
    return JSONResponse(
        status_code=200,
        content=ResponseJson(
            success=True,
            message=ResponseJsonMessage(status_code=200, info="All users"),
            data=[u.to_doc() for u in users],
        ).to_dict(),
    )


async def get_user_by_id(request: Request, user_id: str = QueryParam(...)):
    admin_user, err = await _check_admin_token(request)
    if err:
        return err
    new_user = UserPojo()
    new_user.user_id = user_id
    new_user = await new_user.find_by_user_id()
    if new_user and await new_user.is_exist():
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="User by id"),
                data=new_user.to_doc(),
            ).to_dict(),
        )
    else:
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=404, info="User not found"),
                data={},
            ).to_dict(),
        )


async def get_user_traffic(request: Request, user_id: str = QueryParam(...)):
    admin_user, err = await _check_admin_token(request)
    if err:
        return err
    traffic = TrafficHistory()
    traffic.user_id = user_id
    if await traffic.is_exist():
        history = await traffic.find_by_user_id()
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="User traffic"),
                data=[h.to_doc() for h in history],
            ).to_dict(),
        )
    else:
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(
                    status_code=404, info="User traffic not found"
                ),
                data={},
            ).to_dict(),
        )


async def get_user_codes(request: Request, user_id: str = QueryParam(...)):
    admin_user, err = await _check_admin_token(request)
    if err:
        return err
    code = CodePojo()
    code.user_id = user_id
    if await code.is_exist():
        codes = await code.find_by_user_id()
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="User codes"),
                data=[c.to_doc() for c in codes],
            ).to_dict(),
        )
    else:
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(
                    status_code=404, info="User codes not found"
                ),
                data={},
            ).to_dict(),
        )


async def get_tarriffs(request: Request):
    admin_user, err = await _check_admin_token(request)
    if err:
        return err
    tariffs = await TariffPojo.find_all()
    return JSONResponse(
        status_code=200,
        content=ResponseJson(
            success=True,
            message=ResponseJsonMessage(status_code=200, info="All tariffs"),
            data=[t.to_doc() for t in tariffs],
        ).to_dict(),
    )


async def get_servers(request: Request):
    admin_user, err = await _check_admin_token(request)
    if err:
        return err
    servers = await ServerPojo.find_all()
    return JSONResponse(
        status_code=200,
        content=ResponseJson(
            success=True,
            message=ResponseJsonMessage(status_code=200, info="All servers"),
            data=[s.to_doc() for s in servers],
        ).to_dict(),
    )
