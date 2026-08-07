import logging

from starlette.responses import JSONResponse

from src.db.v3.payments.tariff_pojo import TariffPojo
from src.endpoints.response_object import ResponseJson, ResponseJsonMessage

logger = logging.getLogger(__name__)


async def get_tariff():
    tariffs = await TariffPojo.find_all()
    return JSONResponse(
        status_code=200,
        content=ResponseJson(
            success=True,
            message=ResponseJsonMessage(status_code=200, info="tariffs"),
            data=[t.to_doc() for t in tariffs],
        ).to_dict(),
    )
