# GW protocol — Telegram bot registration patch

## 1. bot/keyboards/admin_menu.py — add GW button to `servers_menu()`

In the `servers_menu()` function, add a GW row before the "⬅️ Назад" button:

```python
def servers_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔐 IKEv2", callback_data="servers:ikev2")],
        [InlineKeyboardButton("⚡ VLESS", callback_data="servers:vless")],
        [InlineKeyboardButton("👽 AWG", callback_data="servers:awg")],
        [InlineKeyboardButton("🌐 GW", callback_data="servers:gw")],      # <-- NEW
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")],
    ])
```

## 2. bot/main.py — import + register handlers

Add the import near the existing `from bot.handlers.admin.servers_awg import ...`:

```python
from bot.handlers.admin.servers_gw import (
    servers_gw, gw_server_info, gw_add_prompt, gw_server_toggle,
    gw_server_prem, gw_server_del, gw_field_prompt, gw_field_set,
    gw_text_router,
)
from telegram import filters
```

Register handlers near the existing awg handlers block (~lines 193-199):

```python
app.add_handler(CallbackQueryHandler(servers_gw, pattern="^servers:gw$"))
app.add_handler(CallbackQueryHandler(gw_add_prompt, pattern=r"^gw_add$"))
app.add_handler(CallbackQueryHandler(gw_server_info, pattern=r"^gw_s:.+$"))
app.add_handler(CallbackQueryHandler(gw_server_toggle, pattern=r"^gw_tog:.+$"))
app.add_handler(CallbackQueryHandler(gw_server_prem, pattern=r"^gw_prem:.+$"))
app.add_handler(CallbackQueryHandler(gw_server_del, pattern=r"^gw_del:.+$"))
app.add_handler(CallbackQueryHandler(gw_field_prompt, pattern=r"^gw_edit:.+$"))
app.add_handler(CallbackQueryHandler(gw_field_set, pattern=r"^gw_set:.+$"))
# text input for field edits + add flow (dispatched by waiting_for)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, gw_text_router))
```

> NOTE: if there is already a `MessageHandler(filters.TEXT ...)` for the existing
> `awg_server_edit_text`, the new `gw_text_router` is compatible — it checks
> `waiting_for` and only acts on `server_gw_edit` / `server_gw_add`, leaving the
> awg values untouched. Register it at a lower priority (after) the awg one if both
> exist, or merge them into a single dispatcher.
