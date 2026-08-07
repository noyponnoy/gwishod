import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

_admins_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = []
for x in _admins_raw.replace(" ", "").split(","):
    if x.isdigit():
        ADMIN_IDS.append(int(x))

API_BASE_URL = os.getenv("API_BASE_URL", "http://10.111.23.229:3002")

# Веб-панель (кнопка Menu / Web App в Telegram). HTTPS обязателен.
PANEL_URL = os.getenv(
    "PANEL_URL",
    "https://api-gwvpn-app.vpnhub.xyz/adminka-android-api/login",
).strip()
