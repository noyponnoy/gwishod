import asyncio
import logging
import uvicorn

from src.logger import init_logger, init_panic_handler
from src.utils.premium_unloader import unload_premium, unload_premium_v3, unload_premium_vless, recreate_users_tick
from src.utils.notificator import periodic_task
from src.old_deleter import delete_users
from src.utils.server_metrics import update_server_metrics_loop, update_ipsec_online_loop
from src.endpoints.server import app

logger = logging.getLogger(__name__)


async def main():
    init_panic_handler()
    init_logger()

    logger.info("API is starting")

    # Start background tasks
    asyncio.create_task(unload_premium())
    asyncio.create_task(unload_premium_v3())
    asyncio.create_task(unload_premium_vless())
    asyncio.create_task(recreate_users_tick())
    asyncio.create_task(periodic_task())
    asyncio.create_task(delete_users())
    asyncio.create_task(update_server_metrics_loop())
    asyncio.create_task(update_ipsec_online_loop())

    logger.info("API is ready")

    config = uvicorn.Config(app, host="0.0.0.0", port=3002, log_level="critical")
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
