import logging
from telegram import BotCommand, MenuButtonWebApp, WebAppInfo
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from bot.config import BOT_TOKEN, PANEL_URL
from bot.handlers.common import start, main_menu_handler, qr_photo_handler
from bot.handlers.admin.unified_text import unified_text_handler
from bot.handlers.admin.users import (
    users_menu_handler, users_all,
    premium_set_prompt, premium_duration_handler,
    premium_revoke_prompt, premium_revoke_confirm,
)
from bot.handlers.admin.subscriptions import (
    subs_menu_handler, tariffs_list, invoices_list,
    tariff_card_handler, tariff_create_prompt, tariff_create_text,
    tariff_edit_prompt, tariff_edit_text,
    tariff_delete_prompt, tariff_delete_confirm,
)
from bot.handlers.admin.analytics import analytics_menu_handler, analytics_summary, analytics_servers
from bot.handlers.admin.servers import (
    servers_menu_handler, servers_ikev2, servers_vless,
    server_card_handler, server_toggle_handler,
    server_edit_prompt, server_edit_text,
    server_delete_prompt, server_delete_confirm,
    vless_card, vless_edit_field_prompt, vless_edit_text,
    vless_delete_prompt, vless_delete_confirm,
    vless_create_start, vless_create_skip,
)
from bot.handlers.admin.settings import settings_menu_handler, admins_list_handler, admin_add_prompt, admin_add_text, admin_remove_handler
from bot.services.api_monitor import api_monitor_job
from bot.handlers.admin.servers_awg import (
    servers_awg,
    awg_server_info,
    awg_server_toggle,
    awg_server_prem,
    awg_server_del,
    awg_server_edit_prompt,
    awg_server_edit_city_prompt,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def on_error(update, context):
    """Глобальный обработчик ошибок: вместо «кнопка молчит» показываем алерт."""
    logger.exception("Ошибка при обработке апдейта", exc_info=context.error)
    try:
        if update and getattr(update, "callback_query", None):
            await update.callback_query.answer(
                f"❌ Ошибка: {str(context.error)[:150]}", show_alert=True
            )
        elif update and getattr(update, "message", None):
            await update.message.reply_text(f"❌ Ошибка: {str(context.error)[:150]}")
    except Exception:
        pass


async def post_init(application: Application) -> None:
    """Команды бота (/start) + кнопка Menu «Открыть веб-панель»."""
    bot = application.bot
    # Список команд у кнопки «/» рядом с полем ввода
    await bot.set_my_commands([
        BotCommand("start", "Старт — обновить меню"),
    ])
    # Синяя кнопка Menu слева внизу у чата с ботом
    if PANEL_URL.startswith("https://"):
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Открыть веб-панель",
                web_app=WebAppInfo(url=PANEL_URL),
            )
        )
        logging.getLogger(__name__).info("Menu WebApp set: %s", PANEL_URL)
    else:
        logging.getLogger(__name__).warning(
            "PANEL_URL не HTTPS — Menu WebApp не установлен: %r", PANEL_URL
        )


def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_error_handler(on_error)

    # Command — /start всегда запускает меню
    app.add_handler(CommandHandler("start", start))
    # Reply-кнопка «Старт» у поля ввода (не inline-меню)
    app.add_handler(MessageHandler(filters.Regex(r"^Старт$"), start))

    # Callback query routing
    app.add_handler(CallbackQueryHandler(main_menu_handler, pattern="^menu:main$"))
    app.add_handler(CallbackQueryHandler(users_menu_handler, pattern="^menu:users$"))
    app.add_handler(CallbackQueryHandler(subs_menu_handler, pattern="^menu:subs$"))
    app.add_handler(CallbackQueryHandler(analytics_menu_handler, pattern="^menu:analytics$"))
    app.add_handler(CallbackQueryHandler(servers_menu_handler, pattern="^menu:servers$"))
    app.add_handler(CallbackQueryHandler(settings_menu_handler, pattern="^menu:settings$"))
    app.add_handler(CallbackQueryHandler(admins_list_handler, pattern="^settings:admins$"))
    app.add_handler(CallbackQueryHandler(admin_add_prompt, pattern="^settings:admin:add$"))
    app.add_handler(CallbackQueryHandler(admin_remove_handler, pattern=r"^settings:admin:remove:\d+$"))

    # Users
    app.add_handler(CallbackQueryHandler(users_all, pattern=r"^users:all:\d+$"))
    app.add_handler(CallbackQueryHandler(premium_set_prompt, pattern="^users:premium:set$"))
    app.add_handler(CallbackQueryHandler(premium_duration_handler, pattern=r"^premium:duration:\d+$"))
    app.add_handler(CallbackQueryHandler(premium_revoke_prompt, pattern="^users:premium:revoke$"))
    app.add_handler(CallbackQueryHandler(premium_revoke_confirm, pattern="^users:premium:revoke_confirm$"))

    # Subscriptions
    app.add_handler(CallbackQueryHandler(tariffs_list, pattern="^subs:tariffs$"))
    app.add_handler(CallbackQueryHandler(tariff_card_handler, pattern=r"^subs:tariff:card:.+$"))
    app.add_handler(CallbackQueryHandler(tariff_create_prompt, pattern="^subs:tariff:create$"))
    app.add_handler(CallbackQueryHandler(tariff_edit_prompt, pattern=r"^subs:tariff:edit:.+$"))
    app.add_handler(CallbackQueryHandler(tariff_delete_prompt, pattern=r"^subs:tariff:delete:[^:]+$"))
    app.add_handler(CallbackQueryHandler(tariff_delete_confirm, pattern=r"^subs:tariff:delete_confirm:.+$"))
    app.add_handler(CallbackQueryHandler(invoices_list, pattern=r"^subs:invoices:\d+$"))

    # Analytics
    app.add_handler(CallbackQueryHandler(analytics_summary, pattern="^analytics:summary$"))
    app.add_handler(CallbackQueryHandler(analytics_servers, pattern="^analytics:servers$"))

    # Servers
    app.add_handler(CallbackQueryHandler(servers_ikev2, pattern="^servers:ikev2$"))
    app.add_handler(CallbackQueryHandler(servers_vless, pattern="^servers:vless$"))
    app.add_handler(CallbackQueryHandler(server_card_handler, pattern=r"^server:card:.+$"))
    app.add_handler(CallbackQueryHandler(server_toggle_handler, pattern=r"^server:toggle:.+$"))
    app.add_handler(CallbackQueryHandler(server_edit_prompt, pattern=r"^server:edit:.+$"))
    app.add_handler(CallbackQueryHandler(server_delete_prompt, pattern=r"^server:delete:[^:]+$"))
    app.add_handler(CallbackQueryHandler(server_delete_confirm, pattern=r"^server:delete_confirm:.+$"))

    # VLESS: в кнопках короткий hash-ID сервера (sid), а не домен —
    # callback_data ограничен 64 байтами, длинные домены его ломали
    app.add_handler(CallbackQueryHandler(vless_create_start, pattern="^vl:add$"))
    app.add_handler(CallbackQueryHandler(vless_create_skip, pattern=r"^vl:skip:.+$"))
    app.add_handler(CallbackQueryHandler(vless_card, pattern=r"^vl:card:.+$"))
    app.add_handler(CallbackQueryHandler(vless_edit_field_prompt, pattern=r"^vl:f:.+$"))
    app.add_handler(CallbackQueryHandler(vless_delete_prompt, pattern=r"^vl:del:.+$"))
    app.add_handler(CallbackQueryHandler(vless_delete_confirm, pattern=r"^vl:delok:.+$"))
    
    app.add_handler(CallbackQueryHandler(servers_awg, pattern="^servers:awg$"))
    app.add_handler(CallbackQueryHandler(awg_server_info, pattern=r"^awg_server:.+$"))
    app.add_handler(CallbackQueryHandler(awg_server_toggle, pattern=r"^awg_toggle:.+$"))
    app.add_handler(CallbackQueryHandler(awg_server_prem, pattern=r"^awg_prem:.+$"))
    app.add_handler(CallbackQueryHandler(awg_server_edit_prompt, pattern=r"^awg_edit:.+$"))
    app.add_handler(CallbackQueryHandler(awg_server_edit_city_prompt, pattern=r"^awg_edit_city:.+$"))
    app.add_handler(CallbackQueryHandler(awg_server_del, pattern=r"^awg_del:.+$"))

    # QR code: photo
    app.add_handler(MessageHandler(filters.PHOTO, qr_photo_handler))

    # All text messages (tariff, server, admin, QR/mnemonic search)
    app.add_handler(MessageHandler(filters.TEXT, unified_text_handler))

    # API Monitor Job
    app.job_queue.run_repeating(api_monitor_job, interval=60, first=5)

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
