from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from bot.config import PANEL_URL


def main_menu():
    rows = []
    # Кнопка Web App — открывает веб-панель внутри Telegram
    if PANEL_URL:
        rows.append([
            InlineKeyboardButton(
                "Открыть веб-панель",
                web_app=WebAppInfo(url=PANEL_URL),
            )
        ])
    rows.extend([
        [InlineKeyboardButton("👤 Пользователи", callback_data="menu:users")],
        [InlineKeyboardButton("💳 Подписки и касса", callback_data="menu:subs")],
        [InlineKeyboardButton("📊 Общая сводка по пользователям", callback_data="analytics:summary")],
        [InlineKeyboardButton("🖥 Общая сводка по серверам", callback_data="analytics:servers")],
        [InlineKeyboardButton("⚡ Управление серверами", callback_data="menu:servers")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="menu:settings")],
    ])
    return InlineKeyboardMarkup(rows)


def start_bottom_kb() -> ReplyKeyboardMarkup:
    """Кнопка «Старт» над полем ввода (не inline-меню разделов).

    Слева у поля занято Menu WebApp («Открыть веб-панель») — Telegram
    не даёт вторую кнопку в том же слоте. Reply-клавиатура — ближайший вариант.
    """
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Старт")]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Старт или поиск…",
    )


def users_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Все юзеры", callback_data="users:all:0")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")],
    ])


def user_card(device_id: str = ""):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Выдать Premium", callback_data="users:premium:set")],
        [InlineKeyboardButton("🚫 Отозвать Premium", callback_data="users:premium:revoke")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:users")],
    ])


def subs_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Список тарифов", callback_data="subs:tariffs")],
        [InlineKeyboardButton("➕ Добавить тариф", callback_data="subs:tariff:create")],
        [InlineKeyboardButton("💰 История платежей", callback_data="subs:invoices:0")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")],
    ])


def tariff_card(technical_name: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Изменить", callback_data=f"subs:tariff:edit:{technical_name}")],
        [InlineKeyboardButton("🗑 Удалить", callback_data=f"subs:tariff:delete:{technical_name}")],
        [InlineKeyboardButton("⬅️ К тарифам", callback_data="subs:tariffs")],
    ])


def confirm_delete_tariff(technical_name: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить удаление", callback_data=f"subs:tariff:delete_confirm:{technical_name}")],
        [InlineKeyboardButton("❌ Отмена", callback_data=f"subs:tariff:card:{technical_name}")],
    ])


def analytics_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Общая сводка по пользователям", callback_data="analytics:summary")],
        [InlineKeyboardButton("🖥 Общая сводка по серверам", callback_data="analytics:servers")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")],
    ])


def servers_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 IKEv2", callback_data="servers:ikev2")],
        [InlineKeyboardButton("⚡ VLESS", callback_data="servers:vless")],
        [InlineKeyboardButton("👽 AWG", callback_data="servers:awg")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")],
    ])


def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")],
    ])


def premium_duration_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1 день", callback_data="premium:duration:1"),
         InlineKeyboardButton("3 дня", callback_data="premium:duration:3")],
        [InlineKeyboardButton("7 дней", callback_data="premium:duration:7"),
         InlineKeyboardButton("30 дней", callback_data="premium:duration:30")],
        [InlineKeyboardButton("90 дней (3 мес)", callback_data="premium:duration:90"),
         InlineKeyboardButton("180 дней (6 мес)", callback_data="premium:duration:180")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:users")],
    ])


def confirm_revoke():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Подтвердить", callback_data="users:premium:revoke_confirm")],
        [InlineKeyboardButton("❌ Отмена", callback_data="menu:users")],
    ])


def back_to_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Главное меню", callback_data="menu:main")],
    ])


def pagination_keyboard(prefix: str, skip: int, total: int, limit: int = 20):
    buttons = []
    if skip > 0:
        buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"{prefix}:{max(0, skip - limit)}"))
    if skip + limit < total:
        buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"{prefix}:{skip + limit}"))
    if buttons:
        return InlineKeyboardMarkup([buttons, [InlineKeyboardButton("🏠 Главное меню", callback_data="menu:main")]])
    return back_to_main()
