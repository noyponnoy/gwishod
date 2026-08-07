from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.config import ADMIN_IDS
from bot.utils.admins_store import get_all_admins, add_admin, remove_admin
from bot.utils.auth import admin_only


@admin_only
async def settings_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Администраторы", callback_data="settings:admins")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")],
    ])
    await query.edit_message_text("⚙️ *Настройки*\n\nВыберите раздел:", reply_markup=kb, parse_mode="Markdown")


@admin_only
async def admins_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    all_admins = get_all_admins()
    root = ADMIN_IDS[0] if ADMIN_IDS else 0

    lines = ["👥 *Администраторы*\n"]
    kb_buttons = []

    lines.append(f"🔑 *Основной:* `{root}` (из .env)")
    kb_buttons.append([InlineKeyboardButton(f"🔑 {root} (основной)", callback_data="settings:admin:root")])

    for admin_id in all_admins:
        lines.append(f"👤 `{admin_id}`")
        if admin_id != root:
            kb_buttons.append([
                InlineKeyboardButton(f"👤 {admin_id}", callback_data=f"settings:admin:info:{admin_id}"),
                InlineKeyboardButton("🗑", callback_data=f"settings:admin:remove:{admin_id}"),
            ])

    kb_buttons.append([InlineKeyboardButton("➕ Добавить администратора", callback_data="settings:admin:add")])
    kb_buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="menu:settings")])

    await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb_buttons), parse_mode="Markdown")


@admin_only
async def admin_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_for"] = "admin_add"
    await query.edit_message_text(
        "➕ Добавить администратора\n\n"
        "Введите Telegram ID пользователя:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="settings:admins")]]),
    )


async def admin_add_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("waiting_for") != "admin_add":
        return
    context.user_data.pop("waiting_for", None)
    text = update.message.text.strip()
    try:
        tg_id = int(text)
    except ValueError:
        await update.message.reply_text("❌ Введите числовой Telegram ID")
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 К списку администраторов", callback_data="settings:admins")],
        [InlineKeyboardButton("➕ Добавить ещё", callback_data="settings:admin:add")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="menu:main")],
    ])
    if add_admin(tg_id):
        await update.message.reply_text(f"✅ Администратор {tg_id} добавлен", reply_markup=kb)
    else:
        await update.message.reply_text(f"⚠️ Администратор {tg_id} уже существует", reply_markup=kb)


@admin_only
async def admin_remove_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tg_id = int(query.data.split(":")[-1])
    if remove_admin(tg_id, ADMIN_IDS):
        await query.edit_message_text(
            f"✅ Администратор `{tg_id}` удалён",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К администраторам", callback_data="settings:admins")]]),
            parse_mode="Markdown",
        )
    else:
        await query.answer("⛔ Нельзя удалить основного администратора", show_alert=True)
