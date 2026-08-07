from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.services.api_client import api
from bot.keyboards.admin_menu import (
    subs_menu, back_to_main, pagination_keyboard,
    tariff_card, confirm_delete_tariff,
)
from bot.utils.auth import admin_only


@admin_only
async def subs_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💳 *Подписки и касса*\n\nВыберите действие:", reply_markup=subs_menu(), parse_mode="Markdown")


# ─── LIST TARIFFS ──────────────────────────────

@admin_only
async def tariffs_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = await api.get("/vpn/api/v1/bot/tariffs/all")
    tariffs = data.get("data", [])
    if not tariffs:
        await query.edit_message_text("💳 Тарифов нет\n\n➕ Добавьте первый тариф", reply_markup=subs_menu())
        return

    text = f"💳 *Тарифы ({len(tariffs)})*\n\nНажмите на тариф для управления:"
    keyboard = []
    for t in tariffs:
        enabled = "✅" if t.get("enabled") else "❌"
        dur_days = int(t.get("duration", 0)) // 86400000
        name = f"{enabled} {t.get('name', 'N/A')} — {t.get('price', 0)} руб / {dur_days} дн"
        tech = t.get("technicalName", "")
        keyboard.append([InlineKeyboardButton(name, callback_data=f"subs:tariff:card:{tech}")])
    keyboard.append([InlineKeyboardButton("➕ Добавить тариф", callback_data="subs:tariff:create")])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu:subs")])
    kb = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")


# ─── TARIFF CARD ───────────────────────────────

@admin_only
async def tariff_card_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    technical_name = query.data.split(":")[-1]
    data = await api.get("/vpn/api/v1/bot/tariffs/get", params={"technical_name": technical_name})
    if data.get("success") != 1:
        await query.edit_message_text("❌ Тариф не найден", reply_markup=back_to_main())
        return
    t = data["data"]
    dur_days = int(t.get("duration", 0)) // 86400000
    dur_hours = (int(t.get("duration", 0)) % 86400000) // 3600000
    enabled = "✅ Включён" if t.get("enabled") else "❌ Выключен"
    text = (
        f"💳 *Карточка тарифа*\n\n"
        f"Название: *{t.get('name', 'N/A')}*\n"
        f"Ключ: `{t.get('technicalName', 'N/A')}`\n"
        f"Описание: {t.get('description', 'Нет')}\n"
        f"Цена: *{t.get('price', 0)}* руб\n"
        f"Длительность: *{dur_days}д {dur_hours}ч* ({t.get('duration', 0)} мс)\n"
        f"Статус: {enabled}\n"
    )
    kb = tariff_card(technical_name)
    await query.edit_message_text(text, reply_markup=kb, parse_mode="Markdown")


# ─── CREATE TARIFF ─────────────────────────────

@admin_only
async def tariff_create_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_for"] = "tariff_create"
    context.user_data["tariff_step"] = "name"
    context.user_data["tariff_data"] = {}
    await query.edit_message_text(
        "➕ Создание тарифа\n\n"
        "Шаг 1/5: Введите название тарифа (например: 1 Month Premium)",
        reply_markup=back_to_main(),
    )


async def tariff_create_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wf = context.user_data.get("waiting_for")
    if wf != "tariff_create":
        return
    step = context.user_data.get("tariff_step", "")
    text = update.message.text.strip()
    data = context.user_data.get("tariff_data", {})

    if step == "name":
        data["name"] = text
        context.user_data["tariff_data"] = data
        context.user_data["tariff_step"] = "technicalName"
        await update.message.reply_text("Шаг 2/5: Введите техническое имя (латиница, без пробелов, например: month1)")
    elif step == "technicalName":
        data["technicalName"] = text
        context.user_data["tariff_data"] = data
        context.user_data["tariff_step"] = "price"
        await update.message.reply_text("Шаг 3/5: Введите цену в рублях (например: 199)")
    elif step == "price":
        data["price"] = text
        context.user_data["tariff_data"] = data
        context.user_data["tariff_step"] = "duration"
        await update.message.reply_text("Шаг 4/5: Введите длительность в миллисекундах\n1 мес = 2592000000\n3 мес = 7776000000\n6 мес = 15552000000")
    elif step == "duration":
        data["duration"] = text
        context.user_data["tariff_data"] = data
        context.user_data["tariff_step"] = "description"
        await update.message.reply_text("Шаг 5/5: Введите описание тарифа")
    elif step == "description":
        data["description"] = text
        context.user_data.pop("waiting_for", None)
        context.user_data.pop("tariff_step", None)
        context.user_data.pop("tariff_data", None)

        result = await api.post("/vpn/api/v1/bot/tariffs/create", data={
            "name": data.get("name", ""),
            "technicalName": data.get("technicalName", ""),
            "price": data.get("price", "0"),
            "duration": data.get("duration", "0"),
            "description": data.get("description", ""),
            "enabled": "true",
        })
        if result.get("success") == 1:
            await update.message.reply_text("✅ Тариф создан!", reply_markup=subs_menu())
        else:
            await update.message.reply_text(f"❌ Ошибка: {result.get('message', 'unknown')}", reply_markup=subs_menu())


# ─── EDIT TARIFF ───────────────────────────────

@admin_only
async def tariff_edit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    technical_name = query.data.split(":")[-1]
    context.user_data["waiting_for"] = "tariff_edit"
    context.user_data["edit_tariff_id"] = technical_name
    context.user_data["tariff_step"] = "name"
    await query.edit_message_text(
        f"✏️ *Изменение тарифа* `{technical_name}`\n\n"
        "Шаг 1/4: Введите новое *название* (или `-` чтобы не менять)",
        reply_markup=back_to_main(),
        parse_mode="Markdown",
    )


async def tariff_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("waiting_for") != "tariff_edit":
        return
    step = context.user_data.get("tariff_step", "")
    text = update.message.text.strip()
    technical_name = context.user_data.get("edit_tariff_id", "")

    if step == "name":
        context.user_data["edit_name"] = text if text != "-" else None
        context.user_data["tariff_step"] = "price"
        await update.message.reply_text("Шаг 2/4: Новая *цена* (или `-`)", parse_mode="Markdown")
    elif step == "price":
        context.user_data["edit_price"] = text if text != "-" else None
        context.user_data["tariff_step"] = "duration"
        await update.message.reply_text("Шаг 3/4: Новая *длительность* в мс (или `-`)", parse_mode="Markdown")
    elif step == "duration":
        context.user_data["edit_duration"] = text if text != "-" else None
        context.user_data["tariff_step"] = "enabled"
        await update.message.reply_text("Шаг 4/4: Включён? (`true`/`false` или `-`)", parse_mode="Markdown")
    elif step == "enabled":
        enabled_val = text if text != "-" else None
        context.user_data.pop("waiting_for", None)
        context.user_data.pop("tariff_step", None)

        post_data = {"technicalName": technical_name}
        name = context.user_data.pop("edit_name", None)
        price = context.user_data.pop("edit_price", None)
        duration = context.user_data.pop("edit_duration", None)
        context.user_data.pop("edit_tariff_id", None)

        if name:
            post_data["name"] = name
        if price:
            post_data["price"] = price
        if duration:
            post_data["duration"] = duration
        if enabled_val:
            post_data["enabled"] = enabled_val

        result = await api.post("/vpn/api/v1/bot/tariffs/update", data=post_data)
        if result.get("success") == 1:
            await update.message.reply_text("✅ Тариф обновлён!", reply_markup=tariff_card(technical_name))
        else:
            await update.message.reply_text(f"❌ Ошибка: {result.get('message', 'unknown')}", reply_markup=subs_menu())


# ─── DELETE TARIFF ─────────────────────────────

@admin_only
async def tariff_delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    technical_name = query.data.split(":")[-1]
    kb = confirm_delete_tariff(technical_name)
    await query.edit_message_text(f"🗑 *Удалить тариф* `{technical_name}`?", reply_markup=kb, parse_mode="Markdown")


@admin_only
async def tariff_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    technical_name = query.data.split(":")[-1]
    result = await api.post("/vpn/api/v1/bot/tariffs/delete", data={"technicalName": technical_name})
    if result.get("success") == 1:
        await query.edit_message_text(f"✅ Тариф `{technical_name}` удалён", reply_markup=subs_menu(), parse_mode="Markdown")
    else:
        await query.edit_message_text(f"❌ Ошибка: {result.get('message', 'unknown')}", reply_markup=subs_menu())


# ─── INVOICES ──────────────────────────────────

@admin_only
async def invoices_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    skip = int(query.data.split(":")[-1])
    data = await api.get("/vpn/api/v1/bot/invoices/all", params={"skip": skip, "limit": 5})
    invoices = data.get("data", [])
    total = data.get("total", 0)
    if not invoices:
        await query.edit_message_text("💰 Платежей нет", reply_markup=back_to_main())
        return
    page = skip // 5 + 1
    pages = (total + 4) // 5
    lines = [f"💰 *Платежи: {total}* (стр. {page}/{pages})\n"]
    for inv in invoices:
        status = inv.get("status", "N/A")
        status_emoji = "✅" if "PAID" in status.upper() else ("⏳" if "CREATED" in status.upper() else "❌")
        plan = inv.get("plan", "N/A")
        amount = inv.get("amount", "0")
        currency = inv.get("currency", "")
        invoice_id = inv.get("invoiceId", "")
        user_id = inv.get("userId", "")
        pay_url = inv.get("payUrl", "")
        created = inv.get("created", "")
        updated = inv.get("updated", "")

        # Форматируем дату
        def _inv_date(dt_str):
            months = ["янв", "фев", "мар", "апр", "мая", "июн",
                      "июл", "авг", "сен", "окт", "ноя", "дек"]
            month_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                         "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
            try:
                dt_str = str(dt_str)
                parts = dt_str.split()
                if len(parts) >= 5:
                    m = month_map.get(parts[1], 0)
                    if m > 0:
                        return f"{parts[2]} {months[m-1]} {parts[4]}, {parts[3]}"
            except Exception:
                pass
            return str(dt_str)[:20]

        created_ru = _inv_date(created)
        updated_ru = _inv_date(updated)

        lines.append(
            f"{status_emoji} *{plan}* — {amount} {currency}\n"
            f"   Статус: `{status}`\n"
            f"   ID: `{invoice_id}`\n"
            f"   UserId: `{user_id}`\n"
            f"   Создан: {created_ru}\n"
        )
    kb = pagination_keyboard("subs:invoices", skip, total, 5)
    await query.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
