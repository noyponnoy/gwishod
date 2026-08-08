"""Обёртки над Telegram Bot API, которые не оставляют интерфейс «висеть».

Зачем этот модуль. У Telegram есть три ограничения, о которые регулярно
спотыкается админка:

1. Текст сообщения — не длиннее 4096 символов. Списки серверов растут,
   и в какой-то момент `edit_message_text` начинает падать с
   «Message is too long». Экран замирает на «Загрузка…».
2. Частота правок одного сообщения. Если долго обновлять экран каждые
   несколько секунд, Telegram отвечает 429 и PTB бросает `RetryAfter` —
   это НЕ `BadRequest`, поэтому обычные `except BadRequest` его пропускают,
   и обработчик умирает молча.
3. Правка тем же текстом — «Message is not modified». Ошибка безобидная,
   но в логах создаёт шум и маскирует настоящие сбои.

Здесь всё это закрыто в одном месте: `safe_edit` сам режет длинный текст по
границам строк, сам ждёт при 429, сам глотает «not modified» и — если
править сообщение всё-таки нельзя — присылает новое, чтобы админ не смотрел
в мёртвый экран.
"""
from __future__ import annotations

import asyncio
import logging

from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError

log = logging.getLogger(__name__)

# Лимит Telegram — 4096. Берём с запасом: эмодзи-флаги и подобные символы
# считаются как 2+ единицы, а нам ещё нужно место под пометку об обрезке.
TEXT_LIMIT = 3900

TRUNCATED_MARK = "\n\n<i>…список обрезан, чтобы уместиться в одно сообщение.</i>"


def clamp_html(text: str, limit: int = TEXT_LIMIT, mark: str = TRUNCATED_MARK) -> str:
    """Укорачивает HTML-текст до лимита, отбрасывая строки с конца.

    Резать посимвольно нельзя — можно разорвать тег и получить
    «Can't parse entities». Строки в наших экранах самодостаточны
    (теги открываются и закрываются внутри строки), поэтому отбрасываем
    целые строки, пока текст не влезет.
    """
    if len(text) <= limit:
        return text

    budget = limit - len(mark)
    lines = text.split("\n")
    kept: list[str] = []
    size = 0
    for line in lines:
        add = len(line) + 1
        if size + add > budget:
            break
        kept.append(line)
        size += add
    if not kept:  # одна гигантская строка — иначе вернём пустоту
        return text[:budget] + mark
    return "\n".join(kept) + mark


async def safe_edit(
    bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup=None,
    parse_mode: str = "HTML",
    fallback_send: bool = True,
) -> bool:
    """Правит сообщение и возвращает True, если экран показан админу.

    fallback_send=True — если править нельзя (сообщение старше 48 часов,
    удалено и т.п.), присылаем новое сообщение вместо тихого провала.
    """
    text = clamp_html(text)

    for attempt in (1, 2):
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
            return True

        except RetryAfter as e:
            # Telegram притормозил этот чат. Ждём столько, сколько просит,
            # но не больше 10 секунд — иначе админ решит, что бот умер.
            wait = min(float(getattr(e, "retry_after", 3)) + 0.5, 10.0)
            log.warning("Telegram просит подождать %.1fs (chat=%s)", wait, chat_id)
            if attempt == 1:
                await asyncio.sleep(wait)
                continue
            break

        except BadRequest as e:
            reason = str(e)
            if "not modified" in reason.lower():
                return True  # на экране уже то, что нужно
            if "too long" in reason.lower() and attempt == 1:
                # Подстраховка: лимит считается в UTF-16, наша оценка могла
                # не сойтись. Режем агрессивнее и пробуем ещё раз.
                text = clamp_html(text, TEXT_LIMIT // 2)
                continue
            log.warning("edit_message_text отказал (chat=%s): %s", chat_id, reason)
            break

        except Forbidden:
            log.info("Админ %s закрыл чат с ботом", chat_id)
            return False

        except TelegramError as e:
            log.warning("Telegram error при правке (chat=%s): %s", chat_id, e)
            break

    if not fallback_send:
        return False

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return True
    except TelegramError as e:
        log.error("Не удалось показать экран админу %s: %s", chat_id, e)
        return False


async def safe_edit_query(query, text: str, reply_markup=None, parse_mode: str = "HTML") -> bool:
    """То же самое, но для callback_query — им пользуются обработчики кнопок."""
    return await safe_edit(
        query.get_bot(),
        query.message.chat_id,
        query.message.message_id,
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )
