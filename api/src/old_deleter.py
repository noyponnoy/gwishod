import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from src.db.v3.a3xui.user_pojo import UserPojo
from src.client_3xui_api.client import delete_user

logger = logging.getLogger(__name__)


async def delete_users():
    while True:
        await asyncio.sleep(60)
        try:
            users = await UserPojo.find_all()
            for user in users:
                zeroes = []
                now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
                zeroes.append(now_ms - user.expired_at.get("1", 0))
                zeroes.append(now_ms - user.expired_at.get("2", 0))
                zero = min(zeroes)
                if zero >= 259200000:
                    if await delete_user(user.tg_id):
                        if await user.delete():
                            async with httpx.AsyncClient() as client:
                                url = f"http://localhost:8080/deleteaccount?tg_id={user.tg_id}"
                                try:
                                    await client.get(url)
                                except Exception as e:
                                    logger.error(str(e))
                elif 86400000 < zero < 259200000 and not user.delnotif:
                    async with httpx.AsyncClient() as client:
                        message = quote("Дорогой пользователь! Если Вы не произведёте оплату в течение 48 часов, то Ваш аккаунт будет удалён в целях повышения Вашей конфиденциальности!")
                        url = f"http://localhost:8080/notification?tg_id={quote(user.tg_id)}&message={message}&image={quote('null')}&type={quote('FULL')}&fileType={quote('null')}"
                        await client.get(url)
                    user.delnotif = True
                    await user.update()
        except Exception as e:
            logger.error(f"Error in delete_users: {e}")
