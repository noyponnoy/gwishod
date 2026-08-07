from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from bot.services.api_client import api
from bot.services.api_monitor import get_api_status_block
from bot.keyboards.admin_menu import analytics_menu, back_to_main
from bot.utils.auth import admin_only
from bot.utils.format import esc, field


@admin_only
async def analytics_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📊 <b>Аналитика</b>\n━━━━━━━━━━━━━━━\nВыберите сводку:",
        reply_markup=analytics_menu(),
        parse_mode="HTML",
    )


# ─── Сводка по пользователям ─────────────────────

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


def _build_summary_text(d: dict) -> str:
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
        "<i>— Автообновление: 3 сек.\n"
        "— В приложении сейчас = заходили за последние 5 мин (не впн подключение)\n"
        "— Неизвестно = юзеры ещё не заходили, так что устройства не определены</i>"
    )


async def _auto_update_summary_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_data = job.data['user_data']
    if user_data.get('auto_update_view') != 'analytics_summary':
        job.schedule_removal()
        return

    data = await api.get("/vpn/api/v1/bot/analytics/summary")
    if data.get("success") != 1:
        return
    try:
        await context.bot.edit_message_text(
            chat_id=job.chat_id,
            message_id=job.data['message_id'],
            text=_build_summary_text(data["data"]),
            reply_markup=back_to_main(),
            parse_mode="HTML",
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            pass
        else:
            job.schedule_removal()
    except Exception:
        job.schedule_removal()


@admin_only
async def analytics_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['auto_update_view'] = 'analytics_summary'

    try:
        await query.edit_message_text("⏳ Загрузка данных по пользователям...", reply_markup=back_to_main())
    except BadRequest:
        pass

    data = await api.get("/vpn/api/v1/bot/analytics/summary")
    if data.get("success") != 1:
        reason = esc(str(data.get("message", "нет ответа"))[:200])
        await query.edit_message_text(f"❌ Ошибка получения данных:\n{reason}", reply_markup=back_to_main(), parse_mode="HTML")
        return

    await query.edit_message_text(
        _build_summary_text(data["data"]),
        reply_markup=back_to_main(),
        parse_mode="HTML",
    )

    for j in context.job_queue.get_jobs_by_name(f"analytics_summary_{update.effective_chat.id}"):
        j.schedule_removal()

    context.job_queue.run_repeating(
        _auto_update_summary_job,
        interval=3,
        chat_id=update.effective_chat.id,
        user_id=update.effective_user.id,
        data={
            "message_id": query.message.message_id,
            "user_data": context.user_data
        },
        name=f"analytics_summary_{update.effective_chat.id}"
    )


# ─── Сводка по серверам ──────────────────────────

def _build_servers_text(d: dict) -> str:
    # IKEv2 онлайн приходит из прямого опроса серверов (node_exporter,
    # метрика ipsec_clients), а не из heartbeat приложения.
    ikev2_connecting = d.get("ikev2Connecting", 0)
    ikev2_connecting_part = f" (🔄 {ikev2_connecting})" if ikev2_connecting else ""
    text = (
        "🖥 <b>Сводка по серверам</b>\n"
        "━━━━━━━━━━━━━━━\n"
        f"📦 Всего серверов: <b>{d.get('totalServers', 0)}</b> "
        f"(🔐 {d.get('ikev2Servers', 0)} · ⚡ {d.get('vlessServers', 0)} · 👽 {d.get('awgServers', 0)})\n\n"
        f"📱 Подключено к VPN: <b>{d.get('totalOnline', 0)}</b>\n"
        f"   🔐 IKEv2: <b>{d.get('ikev2Online', 0)}</b>{ikev2_connecting_part}\n"
        f"   ⚡ VLESS: <b>{d.get('vlessOnline', 0)}</b>\n"
        f"   👽 AWG: <b>{d.get('awgOnline', 0)}</b>\n"
    )

    servers = d.get("servers", [])
    if servers:
        text += "\n🔐 <b>IKEv2</b>\n"
        for s in servers:
            status = "🟢" if s.get("status") else "🔴"
            premium = "⭐ " if s.get("premium") else ""
            connecting = s.get("connectingUsers", 0)
            connecting_part = f" (🔄 {connecting})" if connecting else ""
            # metricsFresh=False — метрики с сервера не получены (сам сервер
            # или его node_exporter недоступен), онлайн показан как 0.
            stale_part = "" if s.get("metricsFresh", True) else " ⚠️"
            text += (
                f"{status} {premium}{esc(field(s.get('country'), 'N/A'))} "
                f"({esc(s.get('ipAddress', 'N/A'))}) — <b>{s.get('onlineUsers', 0)}</b>{connecting_part}{stale_part}\n"
            )

    vless_servers = d.get("vlessServersList", [])
    if vless_servers:
        text += "\n⚡ <b>VLESS</b>\n"
        for s in vless_servers:
            domain = s.get("domain", "")
            if not domain or domain == "0":
                domain = s.get("ipAddress", "N/A")
            desc = field(s.get("description"), "VLESS")
            text += f"⚡ {esc(desc)} ({esc(domain)}) — <b>{s.get('onlineUsers', 0)}</b>\n"

    awg_servers = d.get("awgServersList", [])
    if awg_servers:
        text += "\n👽 <b>AWG</b>\n"
        for s in awg_servers:
            status = "🟢" if s.get("status") else "🔴"
            premium = "⭐ " if s.get("premium") else ""
            text += (
                f"{status} {premium}{esc(field(s.get('country'), 'N/A'))} "
                f"({esc(s.get('ipAddress', 'N/A'))}) — <b>{s.get('onlineUsers', 0)}</b>\n"
            )

    text += (
        "\n<i>🔄 Обновляется автоматически каждые 3 сек.\n"
        "🔐 IKEv2 — данные напрямую с серверов (ipsec_clients, опрос ~60 сек); "
        "🔄 N = подключаются сейчас; ⚠️ = метрики с сервера недоступны.</i>"
    )
    text += esc(get_api_status_block())
    return text


async def _auto_update_servers_job(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    user_data = job.data['user_data']
    if user_data.get('auto_update_view') != 'analytics_servers':
        job.schedule_removal()
        return

    data = await api.get("/vpn/api/v1/bot/servers/stats")
    if data.get("success") != 1:
        return
    try:
        await context.bot.edit_message_text(
            chat_id=job.chat_id,
            message_id=job.data['message_id'],
            text=_build_servers_text(data["data"]),
            reply_markup=back_to_main(),
            parse_mode="HTML",
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            pass
        else:
            job.schedule_removal()
    except Exception:
        job.schedule_removal()


@admin_only
async def analytics_servers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['auto_update_view'] = 'analytics_servers'

    try:
        await query.edit_message_text("⏳ Загрузка данных по серверам...", reply_markup=back_to_main())
    except BadRequest:
        pass

    data = await api.get("/vpn/api/v1/bot/servers/stats")
    if data.get("success") != 1:
        reason = esc(str(data.get("message", "нет ответа"))[:200])
        await query.edit_message_text(f"❌ Ошибка получения данных:\n{reason}", reply_markup=back_to_main(), parse_mode="HTML")
        return

    await query.edit_message_text(
        _build_servers_text(data["data"]),
        reply_markup=back_to_main(),
        parse_mode="HTML",
    )

    for j in context.job_queue.get_jobs_by_name(f"analytics_servers_{update.effective_chat.id}"):
        j.schedule_removal()

    context.job_queue.run_repeating(
        _auto_update_servers_job,
        interval=3,
        chat_id=update.effective_chat.id,
        user_id=update.effective_user.id,
        data={
            "message_id": query.message.message_id,
            "user_data": context.user_data
        },
        name=f"analytics_servers_{update.effective_chat.id}"
    )
