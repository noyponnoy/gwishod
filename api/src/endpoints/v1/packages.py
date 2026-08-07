import logging

from fastapi import APIRouter

from src.db.v2.tariff_pojo import TariffPojo

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/vpn/api/v1/user/packages")
async def get_packages():
    logger.info("User getting packages")
    tariffs = await TariffPojo.find_all()
    packages_data = []
    for tariff in tariffs:
        packages_data.append({
            "_id": tariff.technical_name,
            "createdAt": "",
            "packageName": tariff.name,
            "packageId": tariff.technical_name,
            "packagePricing": int(tariff.price),
            "packagePlatform": "android",
            "packageDuration": tariff.name,
            "__v": 0,
            "id": tariff.technical_name,
        })
    return {
        "success": 1,
        "data": packages_data,
    }
