from fastapi import APIRouter

router = APIRouter()


@router.post("/vpn/api/v1/user/ads")
async def ads():
    return {"success": 1, "data": []}
