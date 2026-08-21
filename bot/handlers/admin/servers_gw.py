"""GW protocol — Telegram bot admin handler.

Mirrors bot/handlers/admin/servers_awg.py in structure (callback-driven, @admin_only,
_safe_edit, HTML parse mode) but extends it with the full per-field editing the GW
protocol requires:
    payload, ssh host/port/user/pass, proxy host/port/scheme, sni, ssh hostkey,
    plus name/country/state/priority and enable/disable, premium toggle, add, delete.

Because GW proxy/SSH hosts are often long Cloudflare domains, we use sid() hashing
(see bot/utils/format.py) for callback_data instead of the raw value — Telegram caps
callback_data at 64 bytes.

Registration (in bot/main.py), next to the awg handlers:
    app.add_handler(CallbackQueryHandler(servers_gw, pattern="^servers:gw$"))
    app.add_handler(CallbackQueryHandler(gw_server_info, pattern=r"^gw_s:.+$"))       # server card
    app.add_handler(CallbackQueryHandler(gw_add_prompt, pattern=r"^gw_add$"))         # add flow
    app.add_handler(CallbackQueryHandler(gw_server_toggle, pattern=r"^gw_tog:.+$"))   # enable/disable
    app.add_handler(CallbackQueryHandler(gw_server_prem, pattern=r"^gw_prem:.+$"))    # premium
    app.add_handler(CallbackQueryHandler(gw_server_del, pattern=r"^gw_del:.+$"))      # delete
    app.add_handler(CallbackQueryHandler(gw_field_prompt, pattern=r"^gw_edit:.+$"))   # choose field
    app.add_handler(CallbackQueryHandler(gw_field_set, pattern=r"^gw_set:.+$"))       # pick field -> prompt
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gw_field_text))   # type new value

And add the "🌐 GW" button to bot/keyboards/admin_menu.py servers_menu().
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from telegram import filters

from bot.services.api_client import api
from bot.utils.auth import admin_only
from bot.utils.format import esc, code, field, sid, resolve_sid


# ---- helpers ----------------------------------------------------------------
async def _safe_edit(query, text: str, reply_markup=None):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise


async def _gw_all():
    """Fetch all GW servers, return list + a {sid: ip} map."""
    data = await api.get("/vpn/api/v1/bot/servers_gw/all")
    # API returns {"ok": True, "servers": [...]} from our new endpoints
    servers = data.get("servers") or data.get("data") or []
    return servers


async def _gw_get(ip: str):
    data = await api.get("/vpn/api/v1/bot/servers_gw/get", params={"server_ip": ip})
    return data.get("server") or data.get("data")


# Editable fields: (api_key, label, hint, multiline?)
# api_key matches the field names accepted by /bot/servers_gw/update
EDITABLE_FIELDS = [
    ("name",          "📛 Название",            "название сервера",            False),
    ("country",       "🏳️ Страна (имя)",        "название страны",             False),
    ("state",         "🏙 Город/регион",        "город или регион",            False),
    ("country_code",  "🔤 Код страны",          "ISO-код (DE, NL, US...)",     False),
    ("ip_address",    "🌐 SSH хост",            "IP или домен SSH-сервера",    False),
    ("ssh_port",      "🔌 SSH порт",            "порт SSH (например 22)",      False),
    ("ssh_username",  "👤 SSH логин",           "имя пользователя SSH",        False),
    ("ssh_password",  "🔑 SSH пароль",          "пароль SSH",                  False),
    ("proxy_host",    "☁️ Proxy хост",          "CDN/прокси хост (Cloudflare)",False),
    ("proxy_port",    "☁️ Proxy порт",          "порт прокси (80/443)",        False),
    ("proxy_scheme",  "🔒 Proxy схема",         "http или https",              False),
    ("payload",       "📨 Payload",             "HTTP-инжектор payload",       True),
    ("sni",           "🆔 SNI",                 "TLS SNI (для CDN fronting)",  False),
    ("ssh_hostkey",   "🔐 Host key (ed25519)",  "ed25519 pub key (опционально)", False),
    ("priority",      "📌 Приоритет",           "число (меньше = выше)",       False),
]


# ---- list view --------------------------------------------------------------
@admin_only
async def servers_gw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    servers = await _gw_all()
    if not servers:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить сервер", callback_data="gw_add")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu:servers")],
        ])
        await _safe_edit(query, "🌐 <b>GW</b>\n\nСерверов пока нет.", reply_markup=kb)
        return

    active = sum(1 for s in servers if s.get("status"))
    text = (
        f"🌐 <b>GW — серверы</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Всего: <b>{len(servers)}</b> · Активных: <b>{active}</b>\n\n"
        f"Нажмите на сервер, чтобы открыть карточку:"
    )
    keyboard = []
    for s in servers:
        ip = s.get("ip_address", "unknown")
        label = s.get("name") or s.get("country") or ip
        status = "🟢" if s.get("status") else "🔴"
        prem = " ⭐" if s.get("premium") else ""
        s_id = sid(ip)
        keyboard.append([InlineKeyboardButton(f"{status} {label} · {ip}{prem}", callback_data=f"gw_s:{s_id}")])

    keyboard.append([
        InlineKeyboardButton("➕ Добавить", callback_data="gw_add"),
        InlineKeyboardButton("🔄 Обновить", callback_data="servers:gw"),
    ])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu:servers")])

    await _safe_edit(query, text, reply_markup=InlineKeyboardMarkup(keyboard))


# ---- server card ------------------------------------------------------------
@admin_only
async def gw_server_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    s_id = query.data.split(":", 1)[1]
    servers = await _gw_all()
    ip = resolve_sid(s_id, [s.get("ip_address", "") for s in servers])
    if not ip:
        await _safe_edit(query, "❌ Сервер не найден",
                         reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="servers:gw")]]))
        return

    server = await _gw_get(ip)
    if not server:
        await _safe_edit(query, "❌ Сервер не найден",
                         reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="servers:gw")]]))
        return

    status = "🟢 Активен" if server.get("status") else "🔴 Выключен"
    premium = "⭐ Платный" if server.get("premium") else "🆓 Бесплатный"
    recommend = "✅ Да" if server.get("recommend") else "—"
    payload_preview = (server.get("payload") or "").replace("\r", "\\r").replace("\n", "\\n")
    if len(payload_preview) > 80:
        payload_preview = payload_preview[:77] + "…"

    name_disp = field(server.get("name")) or field(server.get("country")) or ip
    ssh_disp = f"{field(server.get('ip_address'))}:{field(server.get('ssh_port'), '22')}"
    proxy_disp = (
        f"{field(server.get('proxy_host'))}:{field(server.get('proxy_port'), '80')}"
        f" ({field(server.get('proxy_scheme'), 'http')})"
    )

    text = (
        f"🌐 <b>GW · {esc(name_disp)}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🌐 SSH: {code(ssh_disp)}\n"
        f"👤 Логин: {code(field(server.get('ssh_username'), 'gw'))}\n"
        f"🔑 Пароль: {code(field(server.get('ssh_password'), '••••'))}\n"
        f"☁️ Proxy: {code(proxy_disp)}\n"
        f"🆔 SNI: {code(field(server.get('sni'), '—'))}\n"
        f"📨 Payload: {code(payload_preview or '—')}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🏳️ Страна: {esc(field(server.get('country')))} ({esc(field(server.get('country_code'), '?'))})\n"
        f"🏙 Город: {esc(field(server.get('state')))}\n"
        f"📶 Статус: {status}\n"
        f"💎 Тип: {premium}\n"
        f"📌 Приоритет: {esc(server.get('priority', 0))}\n"
        f"👍 Рекомендуемый: {recommend}"
    )

    toggle_text = "🔴 Выключить" if server.get("status") else "🟢 Включить"
    kb = [
        [
            InlineKeyboardButton(toggle_text, callback_data=f"gw_tog:{s_id}"),
            InlineKeyboardButton("⭐ Прем", callback_data=f"gw_prem:{s_id}"),
        ],
        [InlineKeyboardButton("✏️ Изменить поле", callback_data=f"gw_edit:{s_id}")],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"gw_del:{s_id}")],
        [InlineKeyboardButton("⬅️ К списку", callback_data="servers:gw")],
    ]
    await _safe_edit(query, text, reply_markup=InlineKeyboardMarkup(kb))


# ---- toggle / premium / delete ---------------------------------------------
@admin_only
async def gw_server_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    s_id = query.data.split(":", 1)[1]
    servers = await _gw_all()
    ip = resolve_sid(s_id, [s.get("ip_address", "") for s in servers])
    if ip:
        srv = await _gw_get(ip)
        if srv:
            new_status = not srv.get("status")
            await api.post("/vpn/api/v1/bot/servers_gw/update", data={"ip_address": ip, "status": str(new_status).lower()})
            await query.answer("✅ Статус изменён")
    query.data = f"gw_s:{s_id}"
    await gw_server_info(update, context)


@admin_only
async def gw_server_prem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    s_id = query.data.split(":", 1)[1]
    servers = await _gw_all()
    ip = resolve_sid(s_id, [s.get("ip_address", "") for s in servers])
    if ip:
        srv = await _gw_get(ip)
        if srv:
            new_prem = not srv.get("premium")
            await api.post("/vpn/api/v1/bot/servers_gw/update", data={"ip_address": ip, "premium": str(new_prem).lower()})
            await query.answer("✅ Тип изменён")
    query.data = f"gw_s:{s_id}"
    await gw_server_info(update, context)


@admin_only
async def gw_server_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    s_id = query.data.split(":", 1)[1]
    servers = await _gw_all()
    ip = resolve_sid(s_id, [s.get("ip_address", "") for s in servers])
    if ip:
        await api.post("/vpn/api/v1/bot/servers_gw/delete", data={"ip_address": ip})
        await query.answer("🗑 Удалено", show_alert=True)
    query.data = "servers:gw"
    await servers_gw(update, context)


# ---- field chooser -> prompt ------------------------------------------------
@admin_only
async def gw_field_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the list of editable fields for the chosen server."""
    query = update.callback_query
    await query.answer()
    s_id = query.data.split(":", 1)[1]
    keyboard = []
    # two columns
    row = []
    for key, label, _hint, _ml in EDITABLE_FIELDS:
        row.append(InlineKeyboardButton(label, callback_data=f"gw_set:{s_id}:{key}"))
        if len(row) == 2:
            keyboard.append(row); row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ К серверу", callback_data=f"gw_s:{s_id}")])
    await _safe_edit(query, "✏️ <b>Какое поле изменить?</b>", reply_markup=InlineKeyboardMarkup(keyboard))


@admin_only
async def gw_field_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User picked a field — prompt for the new value via text."""
    query = update.callback_query
    await query.answer()
    # gw_set:<sid>:<field>
    parts = query.data.split(":", 2)
    if len(parts) < 3:
        return
    s_id, fkey = parts[1], parts[2]
    meta = next((f for f in EDITABLE_FIELDS if f[0] == fkey), None)
    if not meta:
        return
    _key, label, hint, multiline = meta
    context.user_data["waiting_for"] = "server_gw_edit"
    context.user_data["gw_edit_sid"] = s_id
    context.user_data["gw_edit_field"] = fkey
    prompt = f"✏️ <b>{label}</b>\n\nОтправьте новое значение ({esc(hint)}):"
    await _safe_edit(
        query, prompt,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Отмена", callback_data=f"gw_s:{s_id}")]]),
    )


async def gw_field_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the new value text and pushes it to the API."""
    if context.user_data.get("waiting_for") != "server_gw_edit":
        return
    s_id = context.user_data.pop("gw_edit_sid", "")
    fkey = context.user_data.pop("gw_edit_field", "")
    context.user_data.pop("waiting_for", None)

    new_val = (update.message.text or "").strip()
    if not new_val:
        await update.message.reply_text("❌ Пустое значение, отмена.")
        return

    servers = await _gw_all()
    ip = resolve_sid(s_id, [s.get("ip_address", "") for s in servers])
    if not ip:
        await update.message.reply_text("❌ Сервер не найден.")
        return

    payload = {"ip_address": ip, fkey: new_val}
    result = await api.post("/vpn/api/v1/bot/servers_gw/update", data=payload)
    ok = result.get("ok") or result.get("success") == 1
    if ok:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К серверу", callback_data=f"gw_s:{s_id}")]])
        await update.message.reply_text(f"✅ Поле обновлено!", reply_markup=kb)
    else:
        await update.message.reply_text(f"❌ {result.get('message', 'ошибка')}")


# ---- add flow ---------------------------------------------------------------
@admin_only
async def gw_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_for"] = "server_gw_add"
    await _safe_edit(
        query,
        "➕ <b>Добавление GW-сервера</b>\n\n"
        "Отправьте строку в формате:\n"
        "<code>name | ssh_host | ssh_port | ssh_user | ssh_pass | proxy_host | proxy_port | payload</code>\n\n"
        "Пример:\n"
        "<code>DE-01 | de1.example.com | 22 | gw | SecRet123 | cf.example.com | 443 | GET / HTTP/1.1[crlf]Host: cf.example.com[crlf]Upgrade: websocket[crlf][crlf]</code>\n\n"
        "<i>proxy_scheme=https, sni и ssh_hostkey будут пустыми — измените их после создания.</i>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Отмена", callback_data="servers:gw")]]),
    )


async def gw_add_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("waiting_for") != "server_gw_add":
        return
    context.user_data.pop("waiting_for", None)
    line = (update.message.text or "").strip()
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 8:
        await update.message.reply_text("❌ Нужно минимум 8 полей, разделённых |. Отмена.")
        return
    name, ssh_host, ssh_port, ssh_user, ssh_pass, proxy_host, proxy_port, payload = parts[:8]
    body = {
        "name": name,
        "ip_address": ssh_host,
        "ssh_port": ssh_port,
        "ssh_username": ssh_user,
        "ssh_password": ssh_pass,
        "proxy_host": proxy_host,
        "proxy_port": proxy_port,
        "proxy_scheme": "https" if str(proxy_port) in ("443", "8443") else "http",
        "payload": payload,
        "country": name,
        "status": "true",
    }
    result = await api.post("/vpn/api/v1/bot/servers_gw/create", data=body)
    ok = result.get("ok") or result.get("success") == 1
    if ok:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К списку GW", callback_data="servers:gw")]])
        await update.message.reply_text("✅ GW-сервер добавлен!", reply_markup=kb)
    else:
        await update.message.reply_text(f"❌ {result.get('message', 'ошибка')}")


# ---- combined text router ---------------------------------------------------
# Register ONE MessageHandler(filters.TEXT & ~filters.COMMAND, gw_text_router)
# that dispatches to gw_field_text / gw_add_text based on waiting_for.
async def gw_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wf = context.user_data.get("waiting_for")
    if wf == "server_gw_edit":
        return await gw_field_text(update, context)
    if wf == "server_gw_add":
        return await gw_add_text(update, context)
