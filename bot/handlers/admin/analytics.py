"""Живые сводки админки: по пользователям и по серверам.

История багфикса. Раздел «Общая сводка по серверам» иногда навсегда
залипал на «Загрузка данных по серверам…»: у одного админа экран мёртвый,
у другого в тот же момент всё рисуется. Причин было три, и все — в этом файле:

1. Экран обновлялся каждые 3 секунды бесконечно, пока админ не нажмёт
   что-то ещё. Уйдя из чата, админ оставлял вечный поток правок одного
   сообщения. Telegram такой темп в одном чате не терпит и начинает отвечать
   429 — PTB бросает `RetryAfter`, а это НЕ `BadRequest`, поэтому прежние
   `except BadRequest` его не ловили. Исключение улетало в глобальный
   обработчик, тот пытался ответить на уже отвеченный callback, падал сам —
   и админ оставался с «Загрузка…» на экране. У второго админа лимит свой,
   поэтому у него всё работало. Отсюда и «иногда» и «а у него норм».
2. Текст сводки не имел ограничения длины: список всех серверов трёх
   протоколов плюс блок мониторинга рано или поздно перерастает лимит
   Telegram в 4096 символов, и правка падает с «Message is too long».
3. Между «Загрузка…» и финальной отрисовкой не было ни одной страховки:
   любая ошибка оставляла админа перед надписью «Загрузка…» без объяснений.

Что сделано: правки идут через `utils/tg.safe_edit` (он режет длинный текст,
переживает 429 и в крайнем случае присылает новое сообщение), автообновление
замедлено, не трогает Telegram, когда данные не изменились, и само
останавливается через 15 минут; любая ошибка теперь видна на экране.
"""
from __future__ import annotations

import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.keyboards.admin_menu import analytics_menu
from bot.services.api_client import api
from bot.services.api_monitor import get_api_status_block
from bot.utils.auth import admin_only
from bot.utils.format import esc, field
from bot.utils.tg import TEXT_LIMIT, safe_edit, safe_edit_query

log = logging.getLogger(__name__)

# Интервал автообновления. Три секунды, как было раньше, — это 20 правок
# одного сообщения в минуту; Telegram начинает притормаживать чат.
AUTO_UPDATE_INTERVAL = 10
# Через сколько автообновление выключается само. Админ, забывший экран
# открытым, больше не создаёт бесконечную нагрузку на API и Telegram.
AUTO_UPDATE_TTL = 15 * 60


def _live_kb(view: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data=_VIEW_CALLBACK[view])],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu:main")],
    ])


@admin_only
async def analytics_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("auto_update_view", None)
    await safe_edit_query(
        query,
        "📊 <b>Аналитика</b>\n━━━━━━━━━━━━━━━\nВыберите сводку:",
        analytics_menu(),
    )


# ═══════════════════════════════════════════════
#  Сводка по пользователям
# ═══════════════════════════════════════════════

def _n(v) -> str:
    """Число с пробелом как разделителем тысяч: 2825 → 2 825."""
    try:
        return f"{int(v):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _plat_block(title: str, b: dict | None, *, last: bool = False) -> str:
    """Дерево метрик по платформе (без эмодзи)."""
    b = b or {}
    total = b.get("total", 0)
    premium = b.get("premium", 0)
    free = b.get("free", 0)
    new24 = b.get("new24h", 0)
    active24 = b.get("active24h", 0)
    online = b.get("onlineNow", 0)
    if last:
        return (
            f"└─ <b>{esc(title)}</b> ({_n(total)})\n"
            f"   ├─ Premium: {_n(premium)} | Free: {_n(free)}\n"
            f"   └─ 24ч: +{_n(new24)} новых | {_n(active24)} активных | {_n(online)} сейчас\n"
        )
    return (
        f"├─ <b>{esc(title)}</b> ({_n(total)})\n"
        f"│  ├─ Premium: {_n(premium)} | Free: {_n(free)}\n"
        f"│  └─ 24ч: +{_n(new24)} новых | {_n(active24)} активных | {_n(online)} сейчас\n"
        f"│\n"
    )


def _build_summary_text(d: dict | None) -> str:
    d = d or {}
    by = d.get("byPlatform") or {}
    return (
        "📊 <b>Сводка по пользователям</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"👥 Всего юзеров: <b>{_n(d.get('total', 0))}</b>\n"
        f"⭐ Premium: <b>{_n(d.get('premium', 0))}</b>\n"
        f"🆓 Free: <b>{_n(d.get('free', 0))}</b>\n"
        f"🆕 Новых за 24ч: <b>{_n(d.get('new24h', 0))}</b>\n"
        f"🟢 Активных за 24ч: <b>{_n(d.get('active24h', 0))}</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"📱 В приложении сейчас: <b>{_n(d.get('onlineNow', 0))}</b>\n"
        f"   ⭐ Premium: {_n(d.get('onlinePremium', 0))}\n"
        f"   🆓 Free: {_n(d.get('onlineFree', 0))}\n"
        "━━━━━━━━━━━━━━━\n"
        "<b>По платформам</b>\n"
        f"{_plat_block('Android', by.get('android'))}"
        f"{_plat_block('iOS', by.get('ios'))}"
        f"{_plat_block('Неизвестно', by.get('unknown'), last=True)}"
        "\n"
        f"<i>— Автообновление: {AUTO_UPDATE_INTERVAL} сек.\n"
        "— В приложении сейчас = заходили за последние 5 мин (не впн подключение)\n"
        "— Неизвестно = юзеры ещё не заходили, так что устройства не определены</i>"
    )


# ═══════════════════════════════════════════════
#  Сводка по серверам
# ═══════════════════════════════════════════════

def _server_line(s: dict, *, icon: str | None = None, show_status: bool = True) -> str:
    status = ("🟢" if s.get("status") else "🔴") if show_status else (icon or "•")
    premium = "⭐ " if s.get("premium") else ""
    connecting = s.get("connectingUsers", 0)
    connecting_part = f" (🔄 {connecting})" if connecting else ""
    # metricsFresh=False — метрики с сервера не получены (сам сервер
    # или его node_exporter недоступен), онлайн показан как 0.
    stale_part = "" if s.get("metricsFresh", True) else " ⚠️"
    return (
        f"{status} {premium}{esc(field(s.get('country'), 'N/A'))} "
        f"({esc(s.get('ipAddress', 'N/A'))}) — <b>{s.get('onlineUsers', 0)}</b>"
        f"{connecting_part}{stale_part}\n"
    )


def _vless_line(s: dict) -> str:
    domain = s.get("domain", "")
    if not domain or domain == "0":
        domain = s.get("ipAddress", "N/A")
    desc = field(s.get("description"), "VLESS")
    return f"⚡ {esc(desc)} ({esc(domain)}) — <b>{s.get('onlineUsers', 0)}</b>\n"


def _build_servers_text(d: dict | None) -> str:
    """Собирает экран сводки, гарантированно укладываясь в лимит Telegram.

    Список серверов растёт, а лимит сообщения — 4096 символов. Поэтому
    сначала считаем заголовок и подвал, а строки серверов добавляем, пока
    есть бюджет: подвал с блоком мониторинга не должен потеряться, а число
    непоместившихся серверов честно показываем.
    """
    # IKEv2 онлайн приходит из прямого опроса серверов (node_exporter,
    # метрика ipsec_clients), а не из heartbeat приложения.
    d = d or {}
    ikev2_connecting = d.get("ikev2Connecting", 0)
    ikev2_connecting_part = f" (🔄 {ikev2_connecting})" if ikev2_connecting else ""
    header = (
        "🖥 <b>Сводка по серверам</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"📦 Всего серверов: <b>{d.get('totalServers', 0)}</b> "
        f"(🔐 {d.get('ikev2Servers', 0)} · ⚡ {d.get('vlessServers', 0)} · 👽 {d.get('awgServers', 0)})\n\n"
        f"📱 Подключено к VPN: <b>{d.get('totalOnline', 0)}</b>\n"
        f"   🔐 IKEv2: <b>{d.get('ikev2Online', 0)}</b>{ikev2_connecting_part}\n"
        f"   ⚡ VLESS: <b>{d.get('vlessOnline', 0)}</b>\n"
        f"   👽 AWG: <b>{d.get('awgOnline', 0)}</b>\n"
    )
    footer = (
        f"\n<i>🔄 Обновляется автоматически каждые {AUTO_UPDATE_INTERVAL} сек "
        f"(и выключается через {AUTO_UPDATE_TTL // 60} мин без действий).\n"
        "🔐 IKEv2 — данные напрямую с серверов (ipsec_clients, опрос каждые 5 сек); "
        "🔄 N = подключаются сейчас; ⚠️ = метрики с сервера недоступны.</i>"
    ) + esc(get_api_status_block())

    # Запас в 150 символов — на пометки «…и ещё N».
    budget = TEXT_LIMIT - len(header) - len(footer) - 150

    body = ""
    sections = (
        ("\n🔐 <b>IKEv2</b>\n", d.get("servers"), _server_line),
        ("\n⚡ <b>VLESS</b>\n", d.get("vlessServersList"), _vless_line),
        ("\n👽 <b>AWG</b>\n", d.get("awgServersList"), _server_line),
    )

    for title, items, render in sections:
        items = items if isinstance(items, list) else []
        if not items:
            continue
        chunk = title
        shown = 0
        for item in items:
            line = render(item if isinstance(item, dict) else {})
            if len(body) + len(chunk) + len(line) > budget:
                break
            chunk += line
            shown += 1
        hidden = len(items) - shown
        if shown == 0:
            chunk += f"<i>{len(items)} шт. — не поместились в сообщение</i>\n"
        elif hidden:
            chunk += f"<i>…и ещё {hidden}</i>\n"
        body += chunk

    return header + body + footer


# ═══════════════════════════════════════════════
#  Механика живых экранов
# ═══════════════════════════════════════════════

_VIEWS = {
    "analytics_summary": {
        "path": "/vpn/api/v1/bot/analytics/summary",
        "build": _build_summary_text,
        "loading": "⏳ Загрузка данных по пользователям…",
        "what": "сводку по пользователям",
    },
    "analytics_servers": {
        "path": "/vpn/api/v1/bot/servers/stats",
        "build": _build_servers_text,
        "loading": "⏳ Загрузка данных по серверам…",
        "what": "сводку по серверам",
    },
}

_VIEW_CALLBACK = {
    "analytics_summary": "analytics:summary",
    "analytics_servers": "analytics:servers",
}


async def _live_update_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Тик автообновления живого экрана.

    Молчит при транзиентных ошибках API, не дёргает Telegram, если текст не
    изменился, и выключается сам, когда админ ушёл или истёк срок.
    """
    job = context.job
    data = job.data
    view = data["view"]
    cfg = _VIEWS[view]

    # Админ переключился на другой раздел — эта задача больше не нужна.
    if data["user_data"].get("auto_update_view") != view:
        job.schedule_removal()
        return

    if time.time() > data["expires_at"]:
        job.schedule_removal()
        data["user_data"].pop("auto_update_view", None)
        if data.get("last_text"):
            await safe_edit(
                context.bot, job.chat_id, data["message_id"],
                data["last_text"] + "\n\n<i>⏸ Автообновление остановлено. Нажмите «Обновить».</i>",
                _live_kb(view), fallback_send=False,
            )
        return

    response = await api.get(cfg["path"])
    if response.get("success") != 1:
        # API моргнул — не рушим экран и не убиваем задачу, просто ждём.
        log.debug("Автообновление %s: API вернул %s", view, response.get("message"))
        return

    try:
        text = cfg["build"](response.get("data"))
    except Exception:  # noqa: BLE001
        log.exception("Автообновление %s: не удалось собрать текст", view)
        job.schedule_removal()
        return

    if text == data.get("last_text"):
        return  # ничего не поменялось — не тратим лимит правок

    shown = await safe_edit(
        context.bot, job.chat_id, data["message_id"], text,
        _live_kb(view), fallback_send=False,
    )
    if shown:
        data["last_text"] = text


async def _open_live_view(update: Update, context: ContextTypes.DEFAULT_TYPE, view: str) -> None:
    """Открывает живой экран: показывает данные и заводит автообновление.

    Гарантия: любая ветка заканчивается видимым сообщением. Экран не может
    остаться на «Загрузка…».
    """
    query = update.callback_query
    cfg = _VIEWS[view]
    await query.answer()
    context.user_data["auto_update_view"] = view

    chat_id = query.message.chat_id
    message_id = query.message.message_id

    await safe_edit_query(query, cfg["loading"], _live_kb(view))

    response = await api.get(cfg["path"])
    if response.get("success") != 1:
        reason = esc(str(response.get("message", "нет ответа"))[:300])
        await safe_edit_query(
            query,
            f"❌ <b>Не удалось получить {esc(cfg['what'])}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Ответ API: <code>{reason}</code>\n\n"
            f"Данные не пришли — сам бот жив. Нажмите «Обновить» через минуту, "
            f"а если повторяется, посмотрите <code>/diag</code>.",
            _live_kb(view),
        )
        return

    try:
        text = cfg["build"](response.get("data"))
    except Exception as e:  # noqa: BLE001
        log.exception("Не удалось собрать экран %s", view)
        await safe_edit_query(
            query,
            f"❌ <b>Данные пришли, но экран не собрался</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"<code>{esc(type(e).__name__)}: {esc(str(e)[:200])}</code>\n\n"
            f"Это ошибка бота, а не API — покажите текст разработчику.",
            _live_kb(view),
        )
        return

    await safe_edit_query(query, text, _live_kb(view))

    if context.job_queue is None:
        log.warning("job_queue недоступен — автообновление экранов работать не будет")
        return

    job_name = f"{view}_{chat_id}"
    for existing in context.job_queue.get_jobs_by_name(job_name):
        existing.schedule_removal()

    context.job_queue.run_repeating(
        _live_update_job,
        interval=AUTO_UPDATE_INTERVAL,
        first=AUTO_UPDATE_INTERVAL,
        chat_id=chat_id,
        user_id=update.effective_user.id,
        name=job_name,
        data={
            "view": view,
            "message_id": message_id,
            "user_data": context.user_data,
            "expires_at": time.time() + AUTO_UPDATE_TTL,
            "last_text": text,
        },
    )


@admin_only
async def analytics_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _open_live_view(update, context, "analytics_summary")


@admin_only
async def analytics_servers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _open_live_view(update, context, "analytics_servers")
