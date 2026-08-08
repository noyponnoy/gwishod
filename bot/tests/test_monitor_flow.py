"""Сквозной тест цикла мониторинга: подставной пингер, подставной API, без сети.

Запуск:  python3 bot/tests/test_monitor_flow.py

Проверяем то, что нельзя проверить чистыми функциями: как открывается и
закрывается инцидент, сколько сообщений реально уходит админам, не приходят
ли дубли на каждом обходе, что попадает в суточную сводку и молчит ли бот
в тихом режиме.
"""
from __future__ import annotations

import asyncio
import os
import sys

os.environ["GEOPINGER_URL"] = "http://127.0.0.1:9"
os.environ["MONITOR_STATE_FILE"] = "/tmp/gw_monitor_flow_state.json"
os.environ["ADMIN_IDS"] = "111,222"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from bot.services.geopinger import Probe  # noqa: E402
from bot.services import vpn_monitor as mon  # noqa: E402

passed = 0
failed: list[str] = []


def check(name: str, got, expected) -> None:
    global passed
    if got == expected:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed.append(f"{name}: ожидали {expected!r}, получили {got!r}")
        print(f"  ❌ {name}: ожидали {expected!r}, получили {got!r}")


def check_in(name: str, needle: str, haystack: str) -> None:
    global passed
    if needle in haystack:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed.append(f"{name}: в тексте нет {needle!r}")
        print(f"  ❌ {name}: в тексте нет {needle!r}\n     ---\n{haystack}\n     ---")


# ── Подставной основной API: три сервера, по одному на протокол ──────────────

class FakeApi:
    async def get(self, path: str, params=None):
        if path.endswith("/bot/servers/all"):
            return {"success": 1, "data": [
                {"ipAddress": "10.0.0.1", "country": "Германия", "state": "Франкфурт",
                 "status": True, "premium": False},
            ]}
        if path.endswith("/bot/servers_awg/all"):
            return {"success": 1, "data": [
                {"ip_address": "10.0.0.2", "country": "Нидерланды", "state": "Амстердам",
                 "status": True, "premium": False},
                {"ip_address": "10.0.0.9", "country": "Выключенный", "state": "—",
                 "status": False, "premium": False},
            ]}
        if path.endswith("/bot/servers_vless/all"):
            return {"success": 1, "data": [
                {"server_ip": "vl01.example.store", "server_domain_port_path": "vl01.example.store:8443",
                 "description": "GWAPP NL01"},
            ]}
        return {"success": 0, "message": "unexpected path"}


# ── Подставной пингер: поведение задаём словарём ─────────────────────────────
# ru/foreign: сколько точек «видят» цель. None = проверка не выполнилась.
WORLD: dict[str, dict] = {}


def _probe(ok: int, total: int, error: str | None = None) -> Probe:
    if error:
        return Probe(error=error)
    return Probe(
        ok=[f"Город{i}" for i in range(ok)],
        bad=[f"Город{i}" for i in range(ok, total)],
        rtt=40,
    )


async def fake_ping(target, countries=None, limit=None):
    return _for(target, countries)


async def fake_tcp(target, ports, countries=None, limit=None):
    return _for(target, countries)


def _for(target: str, countries) -> Probe:
    cfg = WORLD.get(target, {"ru": 6, "foreign": 4})
    is_ru = countries == ["ru"]
    if cfg.get("error"):
        return _probe(0, 0, error=cfg["error"])
    if is_ru:
        return _probe(cfg["ru"], 6)
    return _probe(cfg["foreign"], 4)


class FakeBot:
    def __init__(self):
        self.sent: list[str] = []


SENT: list[str] = []


async def fake_broadcast(bot, text, parse_mode="HTML"):
    SENT.append(text)
    return 2


def reset(fail_streak: int = 2) -> None:
    """Чистое состояние перед каждым сценарием."""
    SENT.clear()
    WORLD.clear()
    mon._state = None
    try:
        os.remove(os.environ["MONITOR_STATE_FILE"])
    except FileNotFoundError:
        pass
    mon.MONITOR_FAIL_STREAK = fail_streak


mon.api = FakeApi()
mon.geopinger.ping = fake_ping
mon.geopinger.tcp = fake_tcp
mon.broadcast_admins = fake_broadcast

bot = FakeBot()
run = asyncio.get_event_loop_policy().new_event_loop().run_until_complete


# ── Сценарий 1: всё работает ────────────────────────────────────────────────
print("\nСценарий 1: все серверы доступны")
reset()
result = run(mon.run_cycle(bot))
check("проверены только включённые серверы", result["targets"], 3)
check("выключенный сервер пропущен", result["summary"][mon.OK], 3)
check("админов не беспокоим", len(SENT), 0)


# ── Сценарий 2: блокировка в РФ ─────────────────────────────────────────────
print("\nСценарий 2: VLESS перестал отвечать из РФ, заграница видит")
reset()
run(mon.run_cycle(bot))                      # первый обход — всё хорошо
WORLD["vl01.example.store"] = {"ru": 0, "foreign": 4}

run(mon.run_cycle(bot))                      # первая неудача — молчим
check("одна неудача не поднимает тревогу", len(SENT), 0)

run(mon.run_cycle(bot))                      # вторая подряд — алерт
check("после второй неудачи пришёл один алерт", len(SENT), 1)
alert = SENT[0]
check_in("в алерте сказано про недоступность из РФ", "недоступен из РФ", alert)
check_in("указан адрес сервера", "vl01.example.store", alert)
check_in("указано название сервера", "GWAPP NL01", alert)
check_in("видно, что проверялись порты", "TCP 22, 8443", alert)
check_in("видно, что заграница отвечает", "Из-за рубежа: 4 из 4", alert)
check_in("названы города, где не отвечает", "Не отвечает:", alert)
check_in("есть время по МСК", "(МСК)", alert)
check_in("вердикт назван словами", "похоже на блокировку", alert)

run(mon.run_cycle(bot))                      # третья — дублей быть не должно
check("повторных алертов по тому же инциденту нет", len(SENT), 1)

# ── Восстановление ──
WORLD["vl01.example.store"] = {"ru": 6, "foreign": 4}
run(mon.run_cycle(bot))
check("о восстановлении сообщили", len(SENT), 2)
recovery = SENT[1]
check_in("сказано, что снова доступен", "снова доступен из РФ", recovery)
check_in("указана длительность простоя", "Не работал", recovery)
check_in("названа причина простоя", "блокировка в РФ", recovery)

# ── Сводка за сутки ──
report = mon.build_daily_report()
check_in("в сводке есть раздел событий", "Отработавшие события: 1", report)
check_in("в сводке назван сервер", "GWAPP NL01", report)
check_in("в сводке указан характер события", "блокировка в РФ", report)
check_in("в сводке есть число обходов", "Циклов проверки", report)


# ── Сценарий 3: сервер лёг целиком ──────────────────────────────────────────
print("\nСценарий 3: сервер не отвечает ни из РФ, ни из-за рубежа")
reset()
WORLD["10.0.0.1"] = {"ru": 0, "foreign": 0}
run(mon.run_cycle(bot))
run(mon.run_cycle(bot))
check("пришёл один алерт", len(SENT), 1)
check_in("формулировка про сам сервер, а не блокировку", "лежит сам сервер", SENT[0])
check_in("заголовок про отсутствие ответа", "не отвечает", SENT[0])


# ── Сценарий 4: частичная деградация ────────────────────────────────────────
print("\nСценарий 4: часть регионов РФ не видит сервер")
reset()
WORLD["10.0.0.2"] = {"ru": 2, "foreign": 4}
run(mon.run_cycle(bot))
run(mon.run_cycle(bot))
check("пришёл алерт о частичной недоступности", len(SENT), 1)
check_in("названа частичная недоступность", "Частичная недоступность", SENT[0])
# При частичной доступности контрольная проверка за рубежом не нужна —
# лишний запрос к пингеру не делаем.
check("контроль за рубежом не запрашивали", "Из-за рубежа" in SENT[0], False)

# Деградация переросла в полную блокировку — это новая информация
WORLD["10.0.0.2"] = {"ru": 0, "foreign": 4}
run(mon.run_cycle(bot))
check("сообщили о смене характера проблемы", len(SENT), 2)
check_in("видно, что было и что стало", "Было: частичная недоступность в РФ", SENT[1])
check_in("новое состояние — блокировка", "стало:", SENT[1])


# ── Сценарий 5: пингер недоступен ───────────────────────────────────────────
print("\nСценарий 5: пингер молчит — аварии не выдумываем")
reset()
for host in ("10.0.0.1", "10.0.0.2", "vl01.example.store"):
    WORLD[host] = {"error": "пингер недоступен"}
run(mon.run_cycle(bot))
run(mon.run_cycle(bot))
# Алерты по серверам начинаются со значка вердикта — их быть не должно.
server_alerts = [t for t in SENT if t.startswith(("🛑", "🔴", "🟠"))]
check("нет ни одного алерта по серверам", server_alerts, [])
check("инциденты не открывались", sum(1 for t in mon.state()["targets"].values() if t["incident"]), 0)
check("зато предупредили, что пингер молчит", any("Пингер не отвечает" in t for t in SENT), True)
check("предупреждение пришло один раз", sum("Пингер не отвечает" in t for t in SENT), 1)

# Пингер вернулся
WORLD.clear()
run(mon.run_cycle(bot))
check("сообщили, что пингер снова работает", any("снова отвечает" in t for t in SENT), True)


# ── Сценарий 6: массовое падение ────────────────────────────────────────────
print("\nСценарий 6: разом отвалились все серверы")
reset()
for host in ("10.0.0.1", "10.0.0.2", "vl01.example.store"):
    WORLD[host] = {"ru": 0, "foreign": 4}
run(mon.run_cycle(bot))
run(mon.run_cycle(bot))
check("вместо трёх сообщений пришло одно сводное", len(SENT), 1)
check_in("это сообщение о массовом сбое", "Массовый сбой", SENT[0])
check_in("перечислены все три сервера", "GWAPP NL01", SENT[0])
check_in("есть подсказка, куда смотреть", "проверьте сеть", SENT[0].lower())


# ── Сценарий 7: тихий режим ─────────────────────────────────────────────────
print("\nСценарий 7: тихий режим")
reset()
mon.mute_for(60)
WORLD["10.0.0.1"] = {"ru": 0, "foreign": 4}
run(mon.run_cycle(bot))
run(mon.run_cycle(bot))
check("в тихом режиме сообщений нет", len(SENT), 0)
report = mon.build_daily_report()
check_in("но событие всё равно попало в сводку", "Не работают прямо сейчас", report)
check_in("в сводке отмечено, что уведомления приглушены", "приглушены", report)
mon.mute_for(0)


# ── Сценарий 8: сервер удалили из панели ────────────────────────────────────
print("\nСценарий 8: удалённый сервер уходит из состояния")
reset()
run(mon.run_cycle(bot))
check("в состоянии три адреса", len(mon.state()["targets"]), 3)


class ShrunkApi(FakeApi):
    async def get(self, path: str, params=None):
        if path.endswith("/bot/servers_vless/all"):
            return {"success": 1, "data": []}
        return await super().get(path, params)


mon.api = ShrunkApi()
run(mon.run_cycle(bot))
check("удалённый сервер убран из состояния", len(mon.state()["targets"]), 2)
mon.api = FakeApi()


# ── Сценарий 9: основной API не отдал список ─────────────────────────────────
print("\nСценарий 9: список серверов получить не удалось")
reset()


class BrokenApi:
    async def get(self, path: str, params=None):
        if path.endswith("/bot/servers_awg/all"):
            return {"success": 0, "message": "connection refused"}
        return await FakeApi().get(path, params)


mon.api = BrokenApi()
result = run(mon.run_cycle(bot))
check("о проблеме со списком сказано явно", result["issues"], ["список AWG получить не удалось"])
check_in("замечание видно в сводке", "список AWG получить не удалось", mon.build_daily_report())
mon.api = FakeApi()


# ── Получатели рассылки ──────────────────────────────────────────────────────
print("\nПолучатели уведомлений")
from bot.utils.notify import admin_recipients  # noqa: E402

recipients = admin_recipients()
# В рассылку идут ВСЕ владельцы из .env (раньше брался только первый)
# плюс админы, добавленные через интерфейс в admins.json.
check("оба владельца из .env получают уведомления", {111, 222} <= set(recipients), True)
check("админы из admins.json тоже в списке", len(recipients) >= 2, True)
check("дублей нет", len(recipients), len(set(recipients)))


print("\n" + "─" * 50)
if failed:
    print(f"❌ Провалено {len(failed)} из {passed + len(failed)}:")
    for item in failed:
        print(f"   • {item}")
    sys.exit(1)
print(f"✅ Все проверки пройдены: {passed}")
