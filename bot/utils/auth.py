from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from bot.config import ADMIN_IDS
from bot.utils.admins_store import is_admin


def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not is_admin(user_id, ADMIN_IDS):
            if update.callback_query:
                await update.callback_query.answer("⛔ У вас нет прав администратора", show_alert=True)
            elif update.message:
                await update.message.reply_text("⛔ У вас нет прав администратора")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
