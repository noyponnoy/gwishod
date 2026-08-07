"""Конфигурация панели администратора.

Все настройки берутся из переменных окружения (.env).
Список админов панели задаётся через PANEL_ADMINS (username:bcrypt-hash,...)
или хранится в отдельном JSON-файле panel_admins.json.
"""
import json
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ─── API сервера (тот же, что у бота) ────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "https://api-gwvpn-app.vpnhub.xyz")
API_DOCS_URL = os.getenv("API_DOCS_URL", f"{API_BASE_URL}/docs")

# ─── JWT ─────────────────────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET") or secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRE_DAYS", "7"))

# ─── Сессия панели ───────────────────────────────────────────────
PANEL_HOST = os.getenv("PANEL_HOST", "0.0.0.0")
PANEL_PORT = int(os.getenv("PANEL_PORT", "8000"))

# Файл хранилища админов панели (рядом с этим модулем).
ADMINS_FILE = Path(__file__).resolve().parent / "panel_admins.json"

# Приватный RSA-ключ для расшифровки QR-кодов приложения.
# Тот же ключ, что использует бот (bot/services/qr_decoder.py).
PRIVATE_RSA_KEY = (
    "30820276020100300D06092A864886F70D0101010500048202603082025C020100028181008C35"
    "F91AB0A69B721771F0E384A9496D336D5732F4392F1A1E5706916CC7814FDCE7A3F4521428D503"
    "B55CCE57FDB6F8E324E6ED25E5C2D179331F06DAC1810E716301BEEF99A8F1D0BFDA7C1A2C11AF"
    "979E8CAE86DC1680516F353E5642E35B01160B5C3A48E56E225201F64E44F4DF1EEB1D4CB80D43"
    "8D4820291E448308BD0203010001028180726617398FA8606C5674C0F6E1E6BDE23B739B1217F2"
    "105C5F24E257054A4257C705B8E03F97F338DA2DBFEB1C20068A4BCA70204E2B8929209A755642"
    "665FC5124E0FF5F5F7C05D06491D9F33C8405DA494784826A9B4F1AD69E7085E9CF7110F4AF36D"
    "01C955ACDFF0C75397A9024ED18C5A767ACE4863FD80D6A2B1549001024100D13E84444FD264B2"
    "238E2B875294373D7EEB4AFEC6E7FE8273160ACCDE5C150EAF6E4765EC2795EB793840D5C936F4"
    "BFAA8E1835C0B4E294D26E5A5F494B541D024100AB8A82F99995ACF0707F2F4CA254591D816748"
    "98C64D6E6B657E4BC0F3F82AC3C92BF72B84901DC447D42A82446B7B7D45A8F34E045835D5592D"
    "09DD6E29252102407F55761444271AD43542ED465A808BE54679559819DF50487E54A999E6AF4E"
    "B93314FF2A0D3E41C39C6F1935804F8B3DA042FC84A992EA57FA7EE14C1F445219024013CA6A2B"
    "F3CD31E3978704E4F98173BA94B85EC6C9721B80267878B2ED32BF74511C526AE1E3629BC791B1"
    "C9CFACFAD54C191EE0EC5D64F095563DE21F187E210241009CBD67C085267DC4FB00F5A24EDA2D"
    "71A328CE30DBB86D165FC94D7BAABE8F593499006849F1D018FFEFB7880E8CAE02F3FC8C599EC4"
    "7DA08730313B9E5E01E7"
)


def _hash_password(plain: str) -> str:
    """Возвращает bcrypt-хэш пароля.

    Использует библиотеку bcrypt напрямую — passlib несовместим с
    bcrypt >= 4.1 (отсутствует __about__), поэтому обходимся без него.
    """
    import bcrypt

    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def _save_admins(admins: list[dict]) -> None:
    """Сохраняет список админов панели в JSON-файл."""
    try:
        with open(ADMINS_FILE, "w", encoding="utf-8") as f:
            json.dump({"admins": admins}, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def _load_admins() -> list[dict]:
    """Загружает список админов панели из JSON-файла.

    При первом запуске создаётся seed-админ admin/admin (bcrypt) — его
    обязательно нужно сменить после первого входа (см. README).
    """
    if not ADMINS_FILE.exists():
        try:
            seed = [{"username": "admin", "password_hash": _hash_password("admin")}]
            _save_admins(seed)
            return seed
        except Exception:
            # Крайний случай — bcrypt недоступен. Возвращаем пустой список,
            # чтобы логин просто не прошёл, а не падал с фейковым хэшем.
            return []
    try:
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "admins" in data:
                return data["admins"]
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []
