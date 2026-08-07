import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from src.db.v1.server_pojo import ServerPojo

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/vpn/api/v1/admin/addServer")
async def add_server(request: Request):
    body = await request.body()
    request_body = body.decode("utf-8")

    params_map: dict[str, str] = {}
    for pair in request_body.split("&"):
        parts = pair.split("=", 1)
        if len(parts) == 2:
            params_map[parts[0]] = parts[1]

    recommend = params_map["recommend"].lower() == "true"
    premium = params_map["premium"].lower() == "true"
    enable = params_map["enable"].lower() == "true"

    ca_file = (
        params_map["caFile"]
        .replace("-----BEGIN CERTIFICATE-----\n", "")
        .replace("\n-----END CERTIFICATE-----", "")
        .replace("\n", "")
        .strip()
    )

    server = ServerPojo()
    server.id = params_map["ipAddress"]
    server.ip_address = params_map["ipAddress"]
    server.country = params_map["country"]
    server.priority = int(params_map["priority"])
    server.u_nsm = params_map["u_nsm"]
    server.p_nsm = params_map["p_nsm"]
    server.ca_file_name = params_map["caFileName"]
    server.ca_file = ca_file
    server.country_code = params_map["countryCode"].lower()
    server.state = params_map["state"]
    server.recommend = recommend
    server.premium = premium
    server.status = enable
    server.created_at = datetime.now(timezone.utc)

    result = await server.insert()

    if result:
        logger.info("Server: %s added", server.id)
        return {
            "success": 1,
            "message": "success",
            "data": server.to_doc(),
        }
    else:
        logger.error("Server: %s add failed", server.id)
        return {
            "success": 0,
            "message": "failed",
            "data": server.to_doc(),
        }
