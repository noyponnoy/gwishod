"""Управление серверами (IKEv2 + VLESS).

Все тексты — HTML (см. utils/format.py), кнопки VLESS используют короткие
hash-ID (sid) вместо сырых доменов: callback_data в Telegram ограничен
64 байтами, и длинный домен в кнопке раньше мог молча ломать обработку.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from bot.services.api_client import api
from bot.keyboards.admin_menu import servers_menu, back_to_main
from bot.utils.auth import admin_only
from bot.utils.format import esc, code, field, sid, resolve_sid


async def _safe_edit(query, text: str, reply_markup=None):
    """edit_message_text, который не падает на 'Message is not modified'."""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise


@admin_only
async def servers_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "🖥 <b>Управление серверами</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "Выберите протокол:"
    )
    await _safe_edit(query, text, reply_markup=servers_menu())


# ════════════════════════════════════════════════
#  IKEv2
# ════════════════════════════════════════════════

@admin_only
async def servers_ikev2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = await api.get("/vpn/api/v1/bot/servers/all")
    servers = data.get("data", [])
    if not servers:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ Назад", callback_data="menu:servers")],
        ])
        await _safe_edit(query, "🔐 <b>IKEv2</b>\n\nСерверов пока нет.", reply_markup=kb)
        return

    active = sum(1 for s in servers if s.get("status"))
    text = (
        f"🔐 <b>IKEv2 — серверы</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Всего: <b>{len(servers)}</b> · Активных: <b>{active}</b>\n\n"
        f"Нажмите на сервер, чтобы открыть карточку:"
    )
    keyboard = []
    for s in servers:
        status = "🟢" if s.get("status") else "🔴"
        premium = " ⭐" if s.get("premium") else ""
        name = f"{status} {s.get('country', 'N/A')} · {s.get('ipAddress', 'N/A')}{premium}"
        keyboard.append([InlineKeyboardButton(name, callback_data=f"server:card:{s.get('ipAddress', '')}")])
    keyboard.append([
        InlineKeyboardButton("🔄 Обновить", callback_data="servers:ikev2"),
        InlineKeyboardButton("⬅️ Назад", callback_data="menu:servers"),
    ])
    await _safe_edit(query, text, reply_markup=InlineKeyboardMarkup(keyboard))


@admin_only
async def server_card_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ip = query.data.split(":", 2)[2]
    data = await api.get("/vpn/api/v1/bot/servers/get", params={"ip_address": ip})
    if data.get("success") != 1:
        await _safe_edit(query, "❌ Сервер не найден", reply_markup=back_to_main())
        return
    s = data["data"]
    status = "🟢 Активен" if s.get("status") else "🔴 Выключен"
    premium = "⭐ Платный" if s.get("premium") else "🆓 Бесплатный"
    text = (
        f"🔐 <b>IKEv2 · {esc(field(s.get('country')))}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🌍 IP: {code(s.get('ipAddress', 'N/A'))}\n"
        f"🏳️ Страна: {esc(field(s.get('country')))} ({esc(field(s.get('countryCode'), '?'))})\n"
        f"🏙 Город: {esc(field(s.get('state')))}\n"
        f"📶 Статус: {status}\n"
        f"💎 Тип: {premium}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 Логин: {code(s.get('u_nsm', 'N/A'))}\n"
        f"🔑 Пароль: {code(s.get('p_nsm', 'N/A'))}\n"
        f"📜 Сертификат: {esc(field(s.get('caFileName')))}"
    )
    toggle_text = "🔴 Выключить" if s.get("status") else "🟢 Включить"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(toggle_text, callback_data=f"server:toggle:{ip}")],
        [
            InlineKeyboardButton("✏️ Имя", callback_data=f"server:edit:{ip}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"server:delete:{ip}"),
        ],
        [InlineKeyboardButton("⬅️ К серверам", callback_data="servers:ikev2")],
    ])
    await _safe_edit(query, text, reply_markup=kb)


@admin_only
async def server_toggle_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    ip = query.data.split(":", 2)[2]
    data = await api.post("/vpn/api/v1/bot/servers/toggle", data={"ipAddress": ip})
    if data.get("success") == 1:
        await query.answer(f"✅ {data.get('message', 'Готово')}", show_alert=False)
        query.data = f"server:card:{ip}"
        await server_card_handler(update, context)
    else:
        await query.answer(f"❌ {data.get('message', 'Ошибка')}", show_alert=True)


@admin_only
async def server_edit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ip = query.data.split(":", 2)[2]
    context.user_data["waiting_for"] = "server_edit"
    context.user_data["edit_server_ip"] = ip
    await _safe_edit(
        query,
        f"✏️ <b>Изменение имени сервера</b> {code(ip)}\n\nОтправьте новое <b>имя (название страны)</b> сообщением:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Отмена", callback_data=f"server:card:{ip}")]]),
    )


async def server_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("waiting_for") != "server_edit":
        return
    text = update.message.text.strip()
    ip = context.user_data.get("edit_server_ip", "")

    context.user_data.pop("waiting_for", None)
    context.user_data.pop("edit_server_ip", None)

    result = await api.post("/vpn/api/v1/bot/servers/update", data={"ipAddress": ip, "country": text})

    if result.get("success") == 1:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К серверу", callback_data=f"server:card:{ip}")]])
        await update.message.reply_text("✅ Имя сервера обновлено!", reply_markup=kb)
    else:
        await update.message.reply_text(f"❌ {result.get('message', 'unknown')}")


@admin_only
async def server_delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ip = query.data.split(":", 2)[2]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Да, удалить", callback_data=f"server:delete_confirm:{ip}")],
        [InlineKeyboardButton("✖️ Отмена", callback_data=f"server:card:{ip}")],
    ])
    await _safe_edit(
        query,
        f"⚠️ <b>Удаление сервера</b>\n\nТочно удалить IKEv2-сервер {code(ip)}?\nДействие необратимо.",
        reply_markup=kb,
    )


@admin_only
async def server_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ip = query.data.split(":", 2)[2]
    result = await api.post("/vpn/api/v1/bot/servers/delete", data={"ipAddress": ip})
    if result.get("success") == 1:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ К серверам", callback_data="servers:ikev2")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="menu:main")],
        ])
        await _safe_edit(query, f"✅ Сервер {code(ip)} удалён", reply_markup=kb)
    else:
        await _safe_edit(query, f"❌ {esc(result.get('message', 'unknown'))}", reply_markup=back_to_main())


# ════════════════════════════════════════════════
#  VLESS — полное управление
# ════════════════════════════════════════════════
#
# callback-схема (короткая, влезает в лимит 64 байта):
#   servers:vless        — список
#   vl:card:<sid>        — карточка сервера
#   vl:f:<поле>:<sid>    — изменить поле (desc/domain/sub/login/pass/sess/tname)
#   vl:del:<sid>         — подтверждение удаления
#   vl:delok:<sid>       — удалить
#   vl:add               — мастер добавления
#
# <sid> = sha1(server_ip)[:12] — сами домены в callback_data не кладём.

VLESS_FIELDS = {
    # ключ: (название для человека, поле API, подсказка для ввода)
    "desc":   ("Название",        "description",                 "Например: 🇳🇱 GWAPP NL01"),
    "domain": ("Домен/порт",      "server_domain_port_path",     "Например: example.com:8443 или просто 8443"),
    "sub":    ("Sub-домен",       "server_domain_port_path_sub", "Домен/порт для подписки (sub)"),
    "login":  ("Логин",           "login",                       "Логин панели"),
    "pass":   ("Пароль",          "password",                    "Пароль панели"),
    "sess":   ("Session",         "session",                     "Session-токен панели"),
    "tname":  ("t_name",          "t_name",                      "Целое число, например 0"),
}


async def _vless_find_by_sid(target_sid: str) -> dict | None:
    """Восстанавливает сервер по короткому sid из кнопки."""
    data = await api.get("/vpn/api/v1/bot/servers_vless/all")
    for s in data.get("data", []):
        if sid(s.get("server_ip", "")) == target_sid:
            return s
    return None


def _vless_title(s: dict) -> str:
    return field(s.get("description"), "VLESS")


def _vless_card_text(s: dict) -> str:
    return (
        f"⚡ <b>VLESS · {esc(_vless_title(s))}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🌍 Адрес: {code(s.get('server_ip', 'N/A'))}\n"
        f"🔌 Домен/порт: {code(field(s.get('server_domain_port_path')))}\n"
        f"📡 Sub-домен: {code(field(s.get('server_domain_port_path_sub')))}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 Логин: {code(field(s.get('login')))}\n"
        f"🔑 Пароль: {code(field(s.get('password')))}\n"
        f"🪪 Session: {code(field(s.get('session')))}\n"
        f"🔢 t_name: {code(s.get('t_name', 0))}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Выберите, что изменить:"
    )


def _vless_card_kb(s_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ Название", callback_data=f"vl:f:desc:{s_id}"),
            InlineKeyboardButton("🔌 Домен/порт", callback_data=f"vl:f:domain:{s_id}"),
        ],
        [
            InlineKeyboardButton("📡 Sub-домен", callback_data=f"vl:f:sub:{s_id}"),
            InlineKeyboardButton("👤 Логин", callback_data=f"vl:f:login:{s_id}"),
        ],
        [
            InlineKeyboardButton("🔑 Пароль", callback_data=f"vl:f:pass:{s_id}"),
            InlineKeyboardButton("🪪 Session", callback_data=f"vl:f:sess:{s_id}"),
        ],
        [
            InlineKeyboardButton("🔢 t_name", callback_data=f"vl:f:tname:{s_id}"),
            InlineKeyboardButton("🗑 Удалить", callback_data=f"vl:del:{s_id}"),
        ],
        [
            InlineKeyboardButton("🔄 Обновить", callback_data=f"vl:card:{s_id}"),
            InlineKeyboardButton("⬅️ К списку", callback_data="servers:vless"),
        ],
    ])


@admin_only
async def servers_vless(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = await api.get("/vpn/api/v1/bot/servers_vless/all")
    servers = data.get("data", [])

    keyboard = []
    if not servers:
        text = "⚡ <b>VLESS</b>\n\nСерверов пока нет — добавьте первый:"
    else:
        text = (
            f"⚡ <b>VLESS — серверы</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Всего: <b>{len(servers)}</b>\n\n"
            f"Нажмите на сервер, чтобы открыть карточку:"
        )
        for s in servers:
            ip = s.get("server_ip", "")
            name = f"⚡ {_vless_title(s)} · {ip}"
            keyboard.append([InlineKeyboardButton(name, callback_data=f"vl:card:{sid(ip)}")])

    keyboard.append([InlineKeyboardButton("➕ Добавить сервер", callback_data="vl:add")])
    keyboard.append([
        InlineKeyboardButton("🔄 Обновить", callback_data="servers:vless"),
        InlineKeyboardButton("⬅️ Назад", callback_data="menu:servers"),
    ])
    await _safe_edit(query, text, reply_markup=InlineKeyboardMarkup(keyboard))


@admin_only
async def vless_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    s_id = query.data.split(":")[-1]
    s = await _vless_find_by_sid(s_id)
    if not s:
        await _safe_edit(
            query,
            "❌ Сервер не найден (возможно, удалён).",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К списку", callback_data="servers:vless")]]),
        )
        return
    await _safe_edit(query, _vless_card_text(s), reply_markup=_vless_card_kb(s_id))


@admin_only
async def vless_edit_field_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # vl:f:<field>:<sid>
    _, _, field_key, s_id = query.data.split(":")
    s = await _vless_find_by_sid(s_id)
    if not s:
        await _safe_edit(query, "❌ Сервер не найден.", reply_markup=back_to_main())
        return

    title, api_field, hint = VLESS_FIELDS[field_key]
    current = s.get(api_field, "0")

    context.user_data["waiting_for"] = "vl_edit"
    context.user_data["vl_edit_ip"] = s.get("server_ip", "")
    context.user_data["vl_edit_field"] = field_key

    await _safe_edit(
        query,
        (
            f"✏️ <b>{esc(title)}</b> — {esc(_vless_title(s))}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Сейчас: {code(field(current))}\n\n"
            f"Отправьте новое значение сообщением.\n"
            f"<i>{esc(hint)}</i>"
        ),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Отмена", callback_data=f"vl:card:{s_id}")]]),
    )


async def vless_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("waiting_for") != "vl_edit":
        return
    value = update.message.text.strip()
    ip = context.user_data.get("vl_edit_ip", "")
    field_key = context.user_data.get("vl_edit_field", "")

    title, api_field, _ = VLESS_FIELDS.get(field_key, ("?", "", ""))

    if field_key == "tname":
        try:
            int(value)
        except ValueError:
            await update.message.reply_text("❌ t_name должен быть целым числом. Попробуйте ещё раз:")
            return  # остаёмся в режиме ожидания ввода

    context.user_data.pop("waiting_for", None)
    context.user_data.pop("vl_edit_ip", None)
    context.user_data.pop("vl_edit_field", None)

    result = await api.post("/vpn/api/v1/bot/servers_vless/update", data={"server_ip": ip, api_field: value})

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К серверу", callback_data=f"vl:card:{sid(ip)}")]])
    if result.get("success") == 1:
        await update.message.reply_text(f"✅ {title} обновлено!", reply_markup=kb)
    else:
        await update.message.reply_text(f"❌ Ошибка: {result.get('message', 'unknown')}", reply_markup=kb)


@admin_only
async def vless_delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    s_id = query.data.split(":")[-1]
    s = await _vless_find_by_sid(s_id)
    if not s:
        await _safe_edit(query, "❌ Сервер не найден.", reply_markup=back_to_main())
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑 Да, удалить", callback_data=f"vl:delok:{s_id}")],
        [InlineKeyboardButton("✖️ Отмена", callback_data=f"vl:card:{s_id}")],
    ])
    await _safe_edit(
        query,
        (
            f"⚠️ <b>Удаление VLESS-сервера</b>\n\n"
            f"Точно удалить <b>{esc(_vless_title(s))}</b> ({code(s.get('server_ip', ''))})?\n"
            f"Действие необратимо."
        ),
        reply_markup=kb,
    )


@admin_only
async def vless_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    s_id = query.data.split(":")[-1]
    s = await _vless_find_by_sid(s_id)
    if not s:
        await _safe_edit(query, "❌ Сервер не найден (возможно, уже удалён).", reply_markup=back_to_main())
        return
    ip = s.get("server_ip", "")
    result = await api.post("/vpn/api/v1/bot/servers_vless/delete", data={"server_ip": ip})
    if result.get("success") == 1:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⬅️ К серверам VLESS", callback_data="servers:vless")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="menu:main")],
        ])
        await _safe_edit(query, f"✅ Сервер {code(ip)} удалён", reply_markup=kb)
    else:
        await _safe_edit(query, f"❌ {esc(result.get('message', 'unknown'))}", reply_markup=back_to_main())


# ─── Мастер добавления VLESS ────────────────────

_VLESS_CREATE_STEPS = [
    # (ключ user_data, заголовок шага, подсказка, обязательное)
    ("ip",     "Адрес сервера",  "IP или домен, например gwapp-nl01.freenets.store", True),
    ("desc",   "Название",       "Например: 🇳🇱 GWAPP NL01", True),
    ("domain", "Домен/порт",     "Например: example.com:8443 или просто 8443", False),
    ("sub",    "Sub-домен",      "Домен/порт подписки (sub)", False),
    ("login",  "Логин",          "Логин панели", False),
    ("pass",   "Пароль",         "Пароль панели", False),
]

_VLESS_CREATE_API_FIELDS = {
    "ip": "server_ip",
    "desc": "description",
    "domain": "server_domain_port_path",
    "sub": "server_domain_port_path_sub",
    "login": "login",
    "pass": "password",
}


def _vless_create_step_kb(step_key: str, required: bool) -> InlineKeyboardMarkup:
    rows = []
    if not required:
        rows.append([InlineKeyboardButton("⏭ Пропустить", callback_data=f"vl:skip:{step_key}")])
    rows.append([InlineKeyboardButton("✖️ Отменить добавление", callback_data="servers:vless")])
    return InlineKeyboardMarkup(rows)


def _vless_create_step_text(idx: int) -> str:
    key, title, hint, required = _VLESS_CREATE_STEPS[idx]
    req = "обязательно" if required else "можно пропустить"
    return (
        f"➕ <b>Новый VLESS-сервер</b> — шаг {idx + 1}/{len(_VLESS_CREATE_STEPS)}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>{esc(title)}</b> <i>({req})</i>\n\n"
        f"Отправьте значение сообщением.\n"
        f"<i>{esc(hint)}</i>"
    )


@admin_only
async def vless_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_for"] = "vl_add"
    context.user_data["vl_add_step"] = 0
    context.user_data["vl_add_data"] = {}
    key, _, _, required = _VLESS_CREATE_STEPS[0]
    await _safe_edit(query, _vless_create_step_text(0), reply_markup=_vless_create_step_kb(key, required))


async def _vless_create_advance(update: Update, context: ContextTypes.DEFAULT_TYPE, value: str | None):
    """Записывает значение текущего шага и двигает мастер дальше."""
    idx = context.user_data.get("vl_add_step", 0)
    data = context.user_data.setdefault("vl_add_data", {})
    key = _VLESS_CREATE_STEPS[idx][0]
    if value is not None:
        data[key] = value

    idx += 1
    if idx < len(_VLESS_CREATE_STEPS):
        context.user_data["vl_add_step"] = idx
        next_key, _, _, required = _VLESS_CREATE_STEPS[idx]
        text = _vless_create_step_text(idx)
        kb = _vless_create_step_kb(next_key, required)
        if update.callback_query:
            await _safe_edit(update.callback_query, text, reply_markup=kb)
        else:
            await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
        return

    # Все шаги пройдены — создаём
    context.user_data.pop("waiting_for", None)
    context.user_data.pop("vl_add_step", None)
    context.user_data.pop("vl_add_data", None)

    post_data = {}
    for k, v in data.items():
        post_data[_VLESS_CREATE_API_FIELDS[k]] = v

    result = await api.post("/vpn/api/v1/bot/servers_vless/create", data=post_data)

    ip = data.get("ip", "")
    if result.get("success") == 1:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Открыть карточку", callback_data=f"vl:card:{sid(ip)}")],
            [InlineKeyboardButton("⬅️ К серверам VLESS", callback_data="servers:vless")],
        ])
        text = f"✅ <b>Сервер добавлен!</b>\n\n⚡ {esc(data.get('desc', 'VLESS'))} · <code>{esc(ip)}</code>"
    else:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К серверам VLESS", callback_data="servers:vless")]])
        text = f"❌ Ошибка добавления: {esc(result.get('message', 'unknown'))}"

    if update.callback_query:
        await _safe_edit(update.callback_query, text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def vless_create_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("waiting_for") != "vl_add":
        return
    await _vless_create_advance(update, context, update.message.text.strip())


@admin_only
async def vless_create_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if context.user_data.get("waiting_for") != "vl_add":
        await _safe_edit(query, "⚠️ Мастер добавления уже завершён.", reply_markup=back_to_main())
        return
    await _vless_create_advance(update, context, None)
