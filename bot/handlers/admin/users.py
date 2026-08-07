from telegram import Update
from telegram.ext import ContextTypes
from bot.services.api_client import api
from bot.keyboards.admin_menu import (
    users_menu, user_card, pagination_keyboard,
    back_to_main, premium_duration_menu, confirm_revoke,
)
from bot.utils.auth import admin_only
from bot.utils.format import esc, code


@admin_only
async def users_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("👤 *Пользователи*\n\nВыберите действие:", reply_markup=users_menu(), parse_mode="Markdown")


@admin_only
async def users_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    skip = int(query.data.split(":")[-1])
    data = await api.get("/vpn/api/v1/bot/users/all", params={"skip": skip, "limit": 10})
    users = data.get("data", [])
    total = data.get("total", 0)
    if not users:
        await query.edit_message_text("👤 Пользователей нет", reply_markup=back_to_main())
        return
    lines = [f"👥 *Всего: {total}* (показано {skip+1}-{skip+len(users)})\n"]
    for u in users:
        status = "⭐" if u.get("isPremium") else "🆓"
        # Метка платформы без эмодзи: Android / iOS / Неизвестно
        plat = (u.get("platform") or "unknown").lower()
        if plat == "ios":
            os_mark = "iOS"
        elif plat == "android":
            os_mark = "Android"
        else:
            os_mark = "Неизвестно"
        lines.append(f"{status} [{os_mark}] `{u.get('id', '?')[:16]}...`")
    kb = pagination_keyboard("users:all", skip, total, 10)
    await query.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")


def _platform_line(u: dict) -> str:
    """Человекочитаемая строка платформы для карточки (без эмодзи)."""
    plat = (u.get("platform") or "unknown").lower()
    if plat == "ios":
        label = "iOS"
    elif plat == "android":
        label = "Android"
    else:
        label = "Неизвестно"
    bundle = (u.get("bundleId") or "").strip()
    if bundle:
        return f"Платформа: {label}\nBundleId: {code(bundle)}\n"
    return f"Платформа: {label}\n"


async def _show_user_card(update, device_id: str, is_message: bool = False, context=None):
    data = await api.get("/vpn/api/v1/bot/users/get", params={"device_id": device_id})
    if data.get("success") != 1:
        reason = data.get("message", "")
        text = f"❌ Пользователь не найден: {code(device_id[:32] + '...')}"
        if reason and reason != "user not found":
            text += f"\n⚠️ Ответ API: {esc(str(reason)[:150])}"
        if is_message:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=back_to_main())
        return
    u = data["data"]
    if context:
        context.user_data["current_device_id"] = u.get("deviceId", device_id)
    def _fmt_date(dt_str):
        if not dt_str or dt_str == "N/A":
            return "N/A"
        months = ["января", "февраля", "марта", "апреля", "мая", "июня",
                  "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        try:
            dt_str = str(dt_str)
            parts = dt_str.split()
            if len(parts) >= 5:
                month_en = parts[1]
                day = parts[2]
                time = parts[3]
                year = parts[4]
                month_map = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                             "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
                m = month_map.get(month_en, 0)
                if m > 0:
                    return f"{day} {months[m - 1]} {year}, {time}"
        except Exception:
            pass
        return str(dt_str)

    is_premium = u.get("isPremium")
    status = "⭐ Premium" if is_premium else "🆓 Free"
    premium_end = _fmt_date(u.get("premiumEnd"))
    premium_line = f"Премиум действует до: {premium_end}" if is_premium else "Премиум не активен"
    country = u.get('countryCode', '0')
    country_line = f"Страна: {country}\n" if country != "0" else ""
    ip = u.get('sourceIp', 'N/A')
    email = u.get('email', 'N/A')
    device_id = u.get('deviceId', 'N/A')
    user_id = u.get('id', 'N/A')

    # Email для анонимных юзеров = deviceId, не показываем отдельно
    if email == device_id or email == user_id:
        email_line = ""
    else:
        email_line = f"Email:\n{code(email)}\n\n"

    text = (
        "👤 <b>Карточка пользователя</b>\n\n"
        f"ID:\n{code(user_id)}\n\n"
        f"DeviceId:\n{code(device_id)}\n\n"
        f"{email_line}"
        f"{_platform_line(u)}"
        f"IP: {code(ip)}\n"
        f"Статус: {status}\n"
        f"{esc(premium_line)}\n"
        f"Анонимный: {'Да' if u.get('isAnonymous') else 'Нет'}\n"
        f"{esc(country_line)}"
        f"Создан: {esc(_fmt_date(u.get('createdAt')))}\n"
        f"Последний вход: {esc(_fmt_date(u.get('lastLogin')))}\n"
        f"Загружено: {u.get('totalUpload', 0)} байт\n"
        f"Скачано: {u.get('totalDownload', 0)} байт\n"
    )
    kb = user_card()
    if is_message:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")


@admin_only
async def premium_set_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⭐ Выберите срок Premium:", reply_markup=premium_duration_menu())


async def premium_duration_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    days = int(query.data.split(":")[-1])
    device_id = context.user_data.get("current_device_id", "")
    data = await api.post("/vpn/api/v1/bot/users/premium/set", data={"deviceId": device_id, "days": str(days)})
    if data.get("success") == 1:
        text = f"✅ Premium выдан на {days} дней\nДо: {data.get('premiumEnd', 'N/A')}"
    else:
        text = f"❌ Ошибка: {data.get('message', 'unknown')}"
    await query.edit_message_text(text, reply_markup=user_card())


@admin_only
async def premium_revoke_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = confirm_revoke()
    await query.edit_message_text("🚫 Отозвать Premium?", reply_markup=kb)


@admin_only
async def premium_revoke_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    device_id = context.user_data.get("current_device_id", "")
    data = await api.post("/vpn/api/v1/bot/users/premium/revoke", data={"deviceId": device_id})
    if data.get("success") == 1:
        text = "✅ Premium отозван"
    else:
        text = f"❌ Ошибка: {data.get('message', 'unknown')}"
    await query.edit_message_text(text, reply_markup=user_card())
