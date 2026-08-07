import logging

from fastapi import Query as QueryParam
from starlette.responses import JSONResponse

from src.db.v3.code.code_pojo import CodePojo
from src.endpoints.response_object import ResponseJson, ResponseJsonMessage

logger = logging.getLogger(__name__)


async def get_all_user_codes(user_id: str = QueryParam(...)):
    codes = CodePojo()
    codes.user_id = user_id
    result = await codes.find_by_user_id()
    return JSONResponse(
        status_code=200,
        content=ResponseJson(
            success=True,
            message=ResponseJsonMessage(status_code=200, info="Codes found"),
            data=[c.to_doc() for c in result],
        ).to_dict(),
    )


async def get_code(code: str = QueryParam(...)):
    code_pojo = CodePojo()
    code_pojo.code = code
    result = await code_pojo.find_by_code()
    if result is None:
        return JSONResponse(
            status_code=404,
            content=ResponseJson(
                success=False,
                message=ResponseJsonMessage(status_code=404, info="Code not found"),
                data={},
            ).to_dict(),
        )
    return JSONResponse(
        status_code=200,
        content=ResponseJson(
            success=True,
            message=ResponseJsonMessage(status_code=200, info="Code found"),
            data=result.to_doc(),
        ).to_dict(),
    )
