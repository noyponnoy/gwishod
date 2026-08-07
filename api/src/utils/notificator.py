import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from src.db.v3.a3xui.user_pojo import UserPojo

logger = logging.getLogger(__name__)


async def periodic_task():
    while True:
        await asyncio.sleep(60)
        try:
            users = await UserPojo.find_all()
            now = int(datetime.now(timezone.utc).timestamp() * 1000)
            for user in users:
                dates = dict(user.expired_at)
                lite = dates.get("1", 0)
                pro = dates.get("2", 0)

                # Lite tariff notifications
                if (lite - now) <= 0:
                    if not user.litenotif0:
                        await _send_notification(user.tg_id, "Тариф Lite закончился")
                        user.litenotif0 = True
                        await user.update()
                elif 0 < (lite - now) <= 86400000:
                    if not user.litenotif1:
                        await _send_notification(user.tg_id, "Тариф Lite закончится через 1 день")
                        user.litenotif1 = True
                        await user.update()
                elif 86400000 < (lite - now) <= 172800000:
                    if not user.litenotif2:
                        await _send_notification(user.tg_id, "Тариф Lite закончится через 2 дня")
                        user.litenotif2 = True
                        await user.update()
                elif 172800000 < (lite - now) <= 259200000:
                    if not user.litenotif3:
                        await _send_notification(user.tg_id, "Тариф Lite закончится через 3 дня")
                        user.litenotif3 = True
                        await user.update()
                else:
                    user.litenotif0 = False
                    user.litenotif1 = False
                    user.litenotif2 = False
                    user.litenotif3 = False
                    await user.update()

                # Pro tariff notifications
                if (pro - now) <= 0:
                    if not user.pronotif0:
                        await _send_notification(user.tg_id, "Тариф Pro закончился")
                        user.pronotif0 = True
                        await user.update()
                elif 0 < (pro - now) <= 86400000:
                    if not user.pronotif1:
                        await _send_notification(user.tg_id, "Тариф Pro закончится через 1 день")
                        user.pronotif1 = True
                        await user.update()
                elif 86400000 < (pro - now) <= 172800000:
                    if not user.pronotif2:
                        await _send_notification(user.tg_id, "Тариф Pro закончится через 2 дня")
                        user.pronotif2 = True
                        await user.update()
                elif 172800000 < (pro - now) <= 259200000:
                    if not user.pronotif3:
                        await _send_notification(user.tg_id, "Тариф Pro закончится через 3 дня")
                        user.pronotif3 = True
                        await user.update()
                else:
                    user.pronotif0 = False
                    user.pronotif1 = False
                    user.pronotif2 = False
                    user.pronotif3 = False
                    await user.update()
        except Exception as e:
            logger.error(f"Error in periodic_task: {e}")


async def _send_notification(tg_id: str, message: str):
    async with httpx.AsyncClient() as client:
        url = (
            f"http://localhost:8080/notification"
            f"?tg_id={quote(tg_id)}"
            f"&message={quote(message)}"
            f"&image={quote('null')}"
            f"&type={quote('ALERT')}"
            f"&fileType={quote('null')}"
        )
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to send notification to {tg_id}: {e}")
