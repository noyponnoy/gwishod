from telegram import Update
from telegram.ext import ContextTypes
from bot.keyboards.admin_menu import main_menu, back_to_main, start_bottom_kb
from bot.services.qr_decoder import decode_qr_from_bytes, decode_qr_from_text
from bot.services.api_client import api
from bot.handlers.admin.users import _show_user_card


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('auto_update_view', None)
    text = (
        "<b>GW VPN — Telegram бот для администрирования</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Выберите нужный раздел в меню ниже\n\n"
        "<i>Для быстрого поиска юзера, просто отправьте QR-код "
        "или мнемонику из 12 слов из приложения</i>"
    )
    if update.message:
        # Сначала закрепляем reply-кнопку «Старт» у поля ввода,
        # затем — inline-меню разделов (в одном message нельзя оба markup).
        if not context.user_data.get("_start_kb_sent"):
            await update.message.reply_text(
                "Кнопка <b>Старт</b> внизу = /start (обновить меню).",
                reply_markup=start_bottom_kb(),
                parse_mode="HTML",
            )
            context.user_data["_start_kb_sent"] = True
        await update.message.reply_text(text, reply_markup=main_menu(), parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=main_menu(), parse_mode="HTML")


async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('auto_update_view', None)
    query = update.callback_query
    await query.answer()
    text = (
        "<b>GW VPN — Telegram бот для администрирования</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Выберите нужный раздел в меню ниже\n\n"
        "<i>Для быстрого поиска юзера, просто отправьте QR-код "
        "или мнемонику из 12 слов из приложения</i>"
    )
    await query.edit_message_text(text, reply_markup=main_menu(), parse_mode="HTML")


async def qr_photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return
    photo = update.message.photo[-1]
    file = await photo.get_file()
    image_bytes = await file.download_as_bytearray()
    device_id = decode_qr_from_bytes(bytes(image_bytes))
    if not device_id:
        await update.message.reply_text("❌ Не удалось распознать QR-код", reply_markup=back_to_main())
        return
    await update.message.reply_text(f"🔍 DeviceId: `{device_id[:32]}...`\nИщу пользователя...", parse_mode="Markdown")
    await _show_user_card(update, device_id, is_message=True, context=context)


async def qr_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()

    # If waiting for input from another handler, let it pass
    if context.user_data.get("waiting_for"):
        return

    if len(text) < 10:
        return

    words = text.split()

    if len(words) == 12:
        await update.message.reply_text("🔍 Определена мнемоника. Ищу пользователя...", parse_mode="Markdown")
        data = await api.get("/vpn/api/v1/bot/users/search_by_mnemonic", params={"mnemonic": text})
        if data.get("success") == 1:
            device_id = data["data"].get("deviceId", "")
            await _show_user_card(update, device_id, is_message=True)
        else:
            await update.message.reply_text(f"❌ {data.get('message', 'Не найдено')}", reply_markup=back_to_main())
    elif ";" in text:
        device_id = decode_qr_from_text(text)
        if device_id:
            await update.message.reply_text(f"🔍 QR расшифрован: `{device_id[:32]}...`\nИщу пользователя...", parse_mode="Markdown")
            await _show_user_card(update, device_id, is_message=True)
        else:
            await update.message.reply_text("❌ Не удалось расшифровать QR-код", reply_markup=back_to_main())
    else:
        await update.message.reply_text(f"🔍 Ищу по ID: `{text[:32]}...`", parse_mode="Markdown")
        await _show_user_card(update, text, is_message=True)


async def diag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/diag — самодиагностика: версии файлов, API, job_queue.

    Помогает мгновенно увидеть «частичный деплой» (когда на сервер
    скопировали не все файлы) и проблемы с API/окружением.
    """
    import hashlib
    import os
    import sys
    import telegram

    lines = ["🩺 Диагностика бота", "━━━━━━━━━━━━━━━"]
    lines.append(f"Python: {sys.version.split()[0]} | PTB: {telegram.__version__}")
    lines.append(f"job_queue: {'✅ есть' if context.job_queue else '❌ НЕТ (авто-обновление не работает!)'}")

    # Версии ключевых файлов (по содержимому): если после деплоя hash
    # отличается от ожидаемого в PR — файл не скопировался / старый.
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files = [
        "main.py", "utils/format.py", "handlers/common.py",
        "handlers/admin/servers.py", "handlers/admin/servers_awg.py",
        "handlers/admin/analytics.py", "handlers/admin/unified_text.py",
        "handlers/admin/users.py", "services/api_client.py",
    ]
    lines.append("\nФайлы (md5/8):")
    for f in files:
        p = os.path.join(base, f)
        try:
            h = hashlib.md5(open(p, "rb").read()).hexdigest()[:8]
            lines.append(f"  {f} — {h}")
        except OSError:
            lines.append(f"  {f} — ❌ ОТСУТСТВУЕТ")

    # Живые проверки API — те самые запросы, что делают «сводка» и поиск юзера
    checks = [
        ("analytics/summary", "/vpn/api/v1/bot/analytics/summary", None),
        ("servers/stats", "/vpn/api/v1/bot/servers/stats", None),
        ("users/get", "/vpn/api/v1/bot/users/get", {"device_id": "diag_test"}),
    ]
    lines.append("\nAPI:")
    import time as _t
    for name, path, params in checks:
        t0 = _t.time()
        r = await api.get(path, params=params)
        ms = int((_t.time() - t0) * 1000)
        if r.get("success") == 1 or r.get("message") == "user not found":
            lines.append(f"  ✅ {name} — OK ({ms}ms)")
        else:
            lines.append(f"  ❌ {name} — {str(r.get('message', 'нет ответа'))[:80]} ({ms}ms)")

    await update.message.reply_text("\n".join(lines))
