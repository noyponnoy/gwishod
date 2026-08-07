from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from bot.services.api_client import api
from bot.utils.auth import admin_only
from bot.utils.format import esc, code, field


async def _safe_edit(query, text: str, reply_markup=None):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise


@admin_only
async def servers_awg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = await api.get("/vpn/api/v1/bot/servers_awg/all")
    servers = data.get("data", [])
    if not servers:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu:servers")],
        ])
        await _safe_edit(query, "👽 <b>AWG</b>\n\nСерверов пока нет.", reply_markup=kb)
        return

    active = sum(1 for s in servers if s.get("status"))
    text = (
        f"👽 <b>AWG — серверы</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Всего: <b>{len(servers)}</b> · Активных: <b>{active}</b>\n\n"
        f"Нажмите на сервер, чтобы открыть карточку:"
    )
    keyboard = []
    for s in servers:
        ip = s.get("ip_address", "unknown")
        country = s.get("country", "Unknown")
        status = "🟢" if s.get("status") else "🔴"
        prem = " ⭐" if s.get("premium") else ""
        keyboard.append([InlineKeyboardButton(f"{status} {country} · {ip}{prem}", callback_data=f"awg_server:{ip}")])

    keyboard.append([
        InlineKeyboardButton("🔄 Обновить", callback_data="servers:awg"),
        InlineKeyboardButton("⬅️ Назад", callback_data="menu:servers"),
    ])
    await _safe_edit(query, text, reply_markup=InlineKeyboardMarkup(keyboard))


@admin_only
async def awg_server_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ip = query.data.split(":", 1)[1]

    data = await api.get("/vpn/api/v1/bot/servers_awg/get", params={"server_ip": ip})
    server = data.get("data")
    if not server:
        await _safe_edit(
            query,
            "❌ Сервер не найден",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="servers:awg")]]),
        )
        return

    status = "🟢 Активен" if server.get("status") else "🔴 Выключен"
    premium = "⭐ Платный" if server.get("premium") else "🆓 Бесплатный"
    recommend = "✅ Да" if server.get("recommend") else "—"
    text = (
        f"👽 <b>AWG · {esc(field(server.get('country')))}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🌍 IP: {code(server.get('ip_address', 'N/A'))}\n"
        f"🏳️ Страна (имя): {esc(field(server.get('country')))}\n"
        f"🏙 Город (регион): {esc(field(server.get('state')))}\n"
        f"🔤 Код страны: {esc(field(server.get('country_code'), '?'))}\n"
        f"📶 Статус: {status}\n"
        f"💎 Тип: {premium}\n"
        f"📌 Приоритет: {esc(server.get('priority', 0))}\n"
        f"👍 Рекомендуемый: {recommend}"
    )

    toggle_text = "🔴 Выключить" if server.get("status") else "🟢 Включить"
    kb = [
        [
            InlineKeyboardButton(toggle_text, callback_data=f"awg_toggle:{ip}"),
            InlineKeyboardButton("⭐ Прем вкл/выкл", callback_data=f"awg_prem:{ip}"),
        ],
        [
            InlineKeyboardButton("✏️ Страна/имя", callback_data=f"awg_edit:{ip}"),
            InlineKeyboardButton("🏙 Город", callback_data=f"awg_edit_city:{ip}"),
        ],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"awg_del:{ip}")],
        [InlineKeyboardButton("⬅️ К списку", callback_data="servers:awg")],
    ]
    await _safe_edit(query, text, reply_markup=InlineKeyboardMarkup(kb))


@admin_only
async def awg_server_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    ip = query.data.split(":", 1)[1]

    data = await api.get("/vpn/api/v1/bot/servers_awg/get", params={"server_ip": ip})
    server = data.get("data")
    if server:
        new_status = not server.get("status")
        await api.post("/vpn/api/v1/bot/servers_awg/update", data={"ip_address": ip, "status": new_status})
        await query.answer("✅ Статус изменён")

    # Refresh info
    query.data = f"awg_server:{ip}"
    await awg_server_info(update, context)


@admin_only
async def awg_server_prem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    ip = query.data.split(":", 1)[1]

    data = await api.get("/vpn/api/v1/bot/servers_awg/get", params={"server_ip": ip})
    server = data.get("data")
    if server:
        new_prem = not server.get("premium")
        await api.post("/vpn/api/v1/bot/servers_awg/update", data={"ip_address": ip, "premium": new_prem})
        await query.answer("✅ Тип изменён")
    query.data = f"awg_server:{ip}"
    await awg_server_info(update, context)


@admin_only
async def awg_server_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    ip = query.data.split(":", 1)[1]
    await api.post("/vpn/api/v1/bot/servers_awg/delete", data={"ip_address": ip})

    await query.answer("🗑 Удалено", show_alert=True)
    query.data = "servers:awg"
    await servers_awg(update, context)


@admin_only
async def awg_server_edit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ip = query.data.split(":", 1)[1]
    context.user_data["waiting_for"] = "server_awg_edit"
    context.user_data["edit_server_awg_ip"] = ip
    await _safe_edit(
        query,
        f"✏️ <b>Изменение имени AWG-сервера</b> {code(ip)}\n\nОтправьте новое <b>имя (название страны)</b> сообщением:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Отмена", callback_data=f"awg_server:{ip}")]]),
    )


@admin_only
async def awg_server_edit_city_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ip = query.data.split(":", 1)[1]
    context.user_data["waiting_for"] = "server_awg_edit_city"
    context.user_data["edit_server_awg_ip"] = ip
    await _safe_edit(
        query,
        f"🏙 <b>Изменение города (региона) AWG-сервера</b> {code(ip)}\n\nОтправьте новое <b>название города/региона</b> сообщением:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Отмена", callback_data=f"awg_server:{ip}")]]),
    )


async def awg_server_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting_for = context.user_data.get("waiting_for")
    if waiting_for not in ["server_awg_edit", "server_awg_edit_city"]:
        return

    new_val = update.message.text.strip()
    ip = context.user_data.get("edit_server_awg_ip", "")

    context.user_data.pop("waiting_for", None)
    context.user_data.pop("edit_server_awg_ip", None)

    if waiting_for == "server_awg_edit":
        result = await api.post("/vpn/api/v1/bot/servers_awg/update", data={"ip_address": ip, "country": new_val})
        msg_success = "✅ Имя AWG-сервера обновлено!"
    else:
        result = await api.post("/vpn/api/v1/bot/servers_awg/update", data={"ip_address": ip, "state": new_val})
        msg_success = "✅ Город (регион) AWG-сервера обновлён!"

    if result.get("success") == 1:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К серверу", callback_data=f"awg_server:{ip}")]])
        await update.message.reply_text(msg_success, reply_markup=kb)
    else:
        await update.message.reply_text(f"❌ {result.get('message', 'unknown')}")
