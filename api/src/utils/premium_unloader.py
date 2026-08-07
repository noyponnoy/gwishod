import asyncio
import logging
from datetime import datetime, timezone

from src.db.v1.user_pojo import UserPojo as UserPojoV1
from src.db.v3.user.user_pojo import UserPojo as UserPojoV3
from src.db.v3.a3xui.user_pojo import UserPojo as UserPojoV3Xui
from src.client_3xui_api.client import unload_user_premium, recreate_user

logger = logging.getLogger(__name__)


async def unload_premium():
    """V1 API: Remove premium status when expired (using bson DateTime comparison)."""
    while True:
        await asyncio.sleep(60)
        try:
            premium_users = await UserPojoV1.find_all_premium()
            now = datetime.utcnow() # Исправлено: теперь используем naive datetime, чтобы не было ошибки "offset-naive and offset-aware datetimes"
            for user in premium_users:
                # Если у пользователя naive дата (без tzinfo) - сравниваем с naive now
                if user.premium_end:
                    user_end = user.premium_end.replace(tzinfo=None) if user.premium_end.tzinfo else user.premium_end
                    if user_end < now:
                        user.is_premium = False
                        await user.update()
        except Exception as e:
            logger.error(f"Error in unload_premium: {e}")


async def unload_premium_v3():
    """V3 API: Disable premium for v3 users when expired."""
    while True:
        await asyncio.sleep(60)
        try:
            users_pojo = UserPojoV3()
            users_pojo.is_premium = True
            premium_users = await UserPojoV3.find_by_premium(users_pojo)
            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            for user in premium_users:
                if user.premium_end < now_ms:
                    user.is_premium = False
                    await user.update()
        except Exception as e:
            logger.error(f"Error in unload_premium_v3: {e}")


async def unload_premium_vless():
    """3XUI/VLESS: Disable VLESS servers when tariff expired."""
    while True:
        await asyncio.sleep(60)
        try:
            users = await UserPojoV3Xui.find_all()
            now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
            for user in users:
                if user.enable.get("1", False) and user.expired_at.get("1", 0) <= now_ms:
                    if await unload_user_premium(user.tg_id, 1):
                        user.enable["1"] = False
                        await user.update()
                if user.enable.get("2", False) and user.expired_at.get("2", 0) <= now_ms:
                    if await unload_user_premium(user.tg_id, 2):
                        user.enable["2"] = False
                        await user.update()
        except Exception as e:
            logger.error(f"Error in unload_premium_vless: {e}")


async def recreate_users_tick():
    """Periodically recreate users on 3XUI servers."""
    while True:
        await asyncio.sleep(60)
        try:
            await recreate_user()
        except Exception as e:
            logger.error(f"Error in recreate_users_tick: {e}")
