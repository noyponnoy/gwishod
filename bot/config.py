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


# ════════════════════════════════════════════════════════════════════════════
#  Мониторинг доступности серверов из РФ (через GEOPinger API)
# ════════════════════════════════════════════════════════════════════════════

def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "да")


def _ints(name: str, default: str) -> list[int]:
    out: list[int] = []
    for chunk in os.getenv(name, default).replace(" ", "").split(","):
        if chunk.isdigit():
            value = int(chunk)
            if 1 <= value <= 65535:
                out.append(value)
    return out


def _words(name: str, default: str) -> list[str]:
    return [
        w.strip().lower()
        for w in os.getenv(name, default).replace(" ", "").split(",")
        if w.strip()
    ]


def _num(name: str, default, cast=int):
    try:
        return cast(os.getenv(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


# Адрес и ключ пингера. Пустой GEOPINGER_URL = мониторинг выключен.
GEOPINGER_URL = os.getenv("GEOPINGER_URL", "").strip().rstrip("/")
GEOPINGER_API_KEY = os.getenv("GEOPINGER_API_KEY", "").strip()
# Проверка на стороне пингера занимает до 45 секунд, клиентский таймаут
# должен быть заметно больше — иначе будем рвать нормальные замеры.
GEOPINGER_TIMEOUT = _num("GEOPINGER_TIMEOUT", 120.0, float)
# Сколько проверок держим в воздухе одновременно. У пингера свой лимит
# (GEOPINGER_MAX_CONCURRENCY, по умолчанию 4) — выше него смысла нет.
GEOPINGER_CONCURRENCY = _num("GEOPINGER_CONCURRENCY", 3)

MONITOR_ENABLED = _flag("MONITOR_ENABLED", True)
# Как часто обходим все адреса, секунды.
MONITOR_INTERVAL_SEC = _num("MONITOR_INTERVAL_SEC", 300)
# Сколько точек берём внутри РФ и сколько за её пределами для контроля.
MONITOR_RU_POINTS = _num("MONITOR_RU_POINTS", 6)
MONITOR_CONTROL_COUNTRIES = _words("MONITOR_CONTROL_COUNTRIES", "kz,br,in,za")
MONITOR_CONTROL_POINTS = _num("MONITOR_CONTROL_POINTS", 4)
# Доля успешных точек РФ, при которой считаем сервер нормально доступным.
MONITOR_OK_RATIO = _num("MONITOR_OK_RATIO", 0.5, float)
# Сколько подряд неудачных циклов нужно, чтобы открыть инцидент (защита
# от единичных сетевых мигов), и сколько удачных — чтобы его закрыть.
MONITOR_FAIL_STREAK = _num("MONITOR_FAIL_STREAK", 2)
MONITOR_OK_STREAK = _num("MONITOR_OK_STREAK", 1)
# Порты для проверки узлов. AWG работает по UDP, снаружи его не пощупать,
# поэтому о доступности судим по управляющему TCP-порту.
MONITOR_AWG_PORTS = _ints("MONITOR_AWG_PORTS", "22")
MONITOR_VLESS_PORTS = _ints("MONITOR_VLESS_PORTS", "22")
# Добавлять к проверке VLESS рабочий порт из настроек сервера (например 8443).
MONITOR_VLESS_USE_CONFIG_PORT = _flag("MONITOR_VLESS_USE_CONFIG_PORT", True)
# Проверять ли выключенные в панели серверы.
MONITOR_INCLUDE_DISABLED = _flag("MONITOR_INCLUDE_DISABLED", False)
# Время суточной сводки и часовой пояс всех отчётов (по умолчанию МСК).
MONITOR_REPORT_TIME = os.getenv("MONITOR_REPORT_TIME", "23:50").strip()
MONITOR_TZ_OFFSET = _num("MONITOR_TZ_OFFSET", 3)
# Напоминать о незакрытых инцидентах раз в N часов (0 — не напоминать).
MONITOR_REMIND_HOURS = _num("MONITOR_REMIND_HOURS", 6, float)
# С какого числа одновременно упавших серверов слать одно сводное
# сообщение вместо отдельного алерта по каждому.
MONITOR_MASS_MIN = _num("MONITOR_MASS_MIN", 3)
# Файл состояния: открытые инциденты и счётчики переживают перезапуск бота.
MONITOR_STATE_FILE = os.getenv(
    "MONITOR_STATE_FILE",
    os.path.join(os.path.dirname(__file__), "monitor_state.json"),
)
