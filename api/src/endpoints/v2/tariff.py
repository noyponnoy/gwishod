import json
import logging

from starlette.responses import PlainTextResponse

from src.db.v2.tariff_pojo import TariffPojo

logger = logging.getLogger(__name__)


async def get_tariff():
    tariffs = await TariffPojo.find_all()
    return PlainTextResponse(
        json.dumps([t.to_doc() for t in tariffs], default=str),
        status_code=200,
    )
