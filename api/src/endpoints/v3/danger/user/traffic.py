import json
import logging

from fastapi import Query, Request
from starlette.responses import JSONResponse

from src.db.v3.user.traffic_history_pojo import TrafficHistory
from src.endpoints.response_object import ResponseJson, ResponseJsonMessage

logger = logging.getLogger(__name__)


async def insert(request: Request):
    body = (await request.body()).decode("utf-8")
    try:
        traffic = TrafficHistory.from_doc(json.loads(body))
    except Exception:
        return JSONResponse(
            status_code=400,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=400, info="Traffic Object error"),
                data={},
            ).to_dict(),
        )

    if await traffic.insert():
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="Traffic inserted"),
                data={},
            ).to_dict(),
        )
    else:
        return JSONResponse(
            status_code=500,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=500, info="Traffic not inserted"),
                data={},
            ).to_dict(),
        )


async def find(user_id: str = Query(...)):
    traffic = TrafficHistory()
    traffic.user_id = user_id
    if await traffic.is_exist():
        history = await traffic.find_by_user_id()
        return JSONResponse(
            status_code=200,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=200, info="User find"),
                data=[h.to_doc() for h in history],
            ).to_dict(),
        )
    else:
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=True,
                message=ResponseJsonMessage(status_code=404, info="User not found"),
                data={},
            ).to_dict(),
        )


async def find_all():
    histories = await TrafficHistory.find_all()
    return JSONResponse(
        status_code=200,
        content=ResponseJson(
            success=True,
            message=ResponseJsonMessage(status_code=200, info="Users found"),
            data=[h.to_doc() for h in histories],
        ).to_dict(),
    )
