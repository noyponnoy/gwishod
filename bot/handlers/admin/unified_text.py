from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.admin.subscriptions import tariff_create_text, tariff_edit_text
from bot.handlers.admin.servers import server_edit_text, vless_edit_text, vless_create_text
from bot.handlers.admin.servers_awg import awg_server_edit_text
from bot.handlers.admin.servers_gw import gw_text_router
from bot.handlers.admin.settings import admin_add_text
from bot.handlers.common import qr_text_handler
from bot.services.qr_decoder import decode_qr_from_text
from bot.services.api_client import api
from bot.handlers.admin.users import _show_user_card
from bot.keyboards.admin_menu import back_to_main


async def unified_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wf = context.user_data.get("waiting_for")

    if wf == "tariff_create":
        await tariff_create_text(update, context)
        return

    if wf == "tariff_edit":
        await tariff_edit_text(update, context)
        return

    if wf == "server_edit":
        await server_edit_text(update, context)
        return

    if wf == "vl_edit":
        await vless_edit_text(update, context)
        return

    if wf == "vl_add":
        await vless_create_text(update, context)
        return

    if wf in ["server_awg_edit", "server_awg_edit_city"]:
        await awg_server_edit_text(update, context)
        return

    if wf in ["server_gw_edit", "server_gw_add"]:
        await gw_text_router(update, context)
        return

    if wf == "admin_add":
        await admin_add_text(update, context)
        return

    # Default: QR / mnemonic / device ID search
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    # Reply-кнопка «Старт» обрабатывается отдельным handler'ом
    if text == "Старт":
        return
    if len(text) < 10:
        return

    words = text.split()

    if len(words) == 12:
        await update.message.reply_text("🔍 Определена мнемоника. Ищу пользователя...")
        data = await api.get("/vpn/api/v1/bot/users/search_by_mnemonic", params={"mnemonic": text})
        if data.get("success") == 1:
            device_id = data["data"].get("deviceId", "")
            await _show_user_card(update, device_id, is_message=True, context=context)
        else:
            await update.message.reply_text(f"❌ {data.get('message', 'Не найдено')}", reply_markup=back_to_main())
    elif ";" in text:
        device_id = decode_qr_from_text(text)
        if device_id:
            await update.message.reply_text(f"🔍 QR расшифрован: `{device_id[:32]}...`\nИщу пользователя...", parse_mode="Markdown")
            await _show_user_card(update, device_id, is_message=True, context=context)
        else:
            await update.message.reply_text("❌ Не удалось расшифровать QR-код", reply_markup=back_to_main())
    else:
        await update.message.reply_text(f"🔍 Ищу по ID: `{text[:32]}...`", parse_mode="Markdown")
        await _show_user_card(update, text, is_message=True, context=context)
