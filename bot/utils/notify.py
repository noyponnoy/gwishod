"""Рассылка служебных сообщений администраторам.

Получатели складываются из двух источников: ADMIN_IDS из .env (владельцы,
их нельзя снять через интерфейс) и admins.json (добавленные через раздел
«Настройки»). Раньше рассылка брала из .env только первого админа —
остальные владельцы уведомлений не получали.
"""
from __future__ import annotations

import asyncio
import logging

from telegram.error import Forbidden, RetryAfter, TelegramError

from bot.config import ADMIN_IDS
from bot.utils.admins_store import get_all_admins

log = logging.getLogger(__name__)


def admin_recipients() -> list[int]:
    """Все, кому уходят служебные уведомления, без дублей."""
    seen: dict[int, None] = {}
    for tg_id in list(ADMIN_IDS) + list(get_all_admins()):
        try:
            seen[int(tg_id)] = None
        except (TypeError, ValueError):
            continue
    return list(seen)


async def broadcast_admins(bot, text: str, parse_mode: str | None = "HTML") -> int:
    """Отправляет текст всем админам. Возвращает число доставленных сообщений.

    Отправка последовательная с небольшой паузой: Telegram не любит
    веер сообщений в один момент, а админов у нас единицы.
    """
    delivered = 0
    for admin_id in admin_recipients():
        for attempt in (1, 2):
            try:
                await bot.send_message(chat_id=admin_id, text=text, parse_mode=parse_mode)
                delivered += 1
                break
            except RetryAfter as e:
                wait = min(float(getattr(e, "retry_after", 3)) + 0.5, 15.0)
                if attempt == 1:
                    await asyncio.sleep(wait)
                    continue
                log.warning("Не смогли уведомить %s: Telegram тормозит", admin_id)
            except Forbidden:
                log.info("Админ %s заблокировал бота — пропускаем", admin_id)
                break
            except TelegramError as e:
                log.warning("Не смогли уведомить %s: %s", admin_id, e)
                break
        await asyncio.sleep(0.05)
    return delivered
