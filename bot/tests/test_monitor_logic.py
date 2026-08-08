"""Тесты логики мониторинга — без сети и без Telegram.

Запуск:  python3 bot/tests/test_monitor_logic.py

Проверяем самое дорогое в этом модуле: правила, по которым мы решаем, что
сервер заблокирован в РФ, а не упал, и разбор ответов пингера. Ошибка здесь
стоит ложных ночных алертов, поэтому логика вынесена в чистые функции.
"""
from __future__ import annotations

import os
import sys

# Модуль читает настройки из окружения при импорте — задаём их до импорта.
os.environ.setdefault("GEOPINGER_URL", "http://127.0.0.1:9")
os.environ.setdefault("MONITOR_STATE_FILE", "/tmp/gw_monitor_test_state.json")

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


def probe(ok: int, bad: int, error: str | None = None) -> Probe:
    return Probe(
        method="ping",
        target="test",
        ok=[f"ok{i}" for i in range(ok)],
        bad=[f"bad{i}" for i in range(bad)],
        error=error,
    )


print("\nВердикты по результатам проверок")
check("все точки РФ отвечают", mon.classify(probe(6, 0), None), mon.OK)
check("большинство точек РФ отвечает", mon.classify(probe(4, 2), None), mon.OK)
check("ровно половина — ещё норма", mon.classify(probe(3, 3), None), mon.OK)
check("отвечает меньшинство — деградация", mon.classify(probe(2, 4), None), mon.DEGRADED)
check("одна точка из шести — деградация", mon.classify(probe(1, 5), None), mon.DEGRADED)
check(
    "РФ молчит, заграница отвечает — блокировка",
    mon.classify(probe(0, 6), probe(4, 0)),
    mon.RU_BLOCKED,
)
check(
    "не отвечает нигде — упал сервер",
    mon.classify(probe(0, 6), probe(0, 4)),
    mon.DOWN,
)
check(
    "РФ молчит, контроль не выполнился — не выдумываем блокировку",
    mon.classify(probe(0, 6), probe(0, 0, error="пингер недоступен")),
    mon.DOWN,
)
check(
    "заграница видит хотя бы одной точкой — уже блокировка",
    mon.classify(probe(0, 6), probe(1, 3)),
    mon.RU_BLOCKED,
)
check(
    "пингер не ответил — вердикта нет, алертов нет",
    mon.classify(probe(0, 0, error="пингер недоступен"), None),
    mon.UNKNOWN,
)
check(
    "пустой результат без ошибки — тоже нет данных",
    mon.classify(probe(0, 0), None),
    mon.UNKNOWN,
)

print("\nРазбор поля «домен/порт» из базы")
check("домен с портом", mon.parse_domain_port("example.com:8443"), ("example.com", 8443))
check("домен с портом и путём", mon.parse_domain_port("example.com:2096/vless"), ("example.com", 2096))
check("только порт", mon.parse_domain_port("8443"), (None, 8443))
check("только домен", mon.parse_domain_port("gwapp-nl01.freenets.store"), ("gwapp-nl01.freenets.store", None))
check("заглушка «0»", mon.parse_domain_port("0"), (None, None))
check("пусто", mon.parse_domain_port(""), (None, None))
check("None", mon.parse_domain_port(None), (None, None))
check("мусорный порт", mon.parse_domain_port("example.com:99999"), ("example.com", None))

print("\nЧеловеческая длительность")
check("секунды", mon.human_duration(45), "45 сек")
check("минуты", mon.human_duration(35 * 60), "35 мин")
check("час ровно", mon.human_duration(3600), "1 ч")
check("час с минутами", mon.human_duration(3600 + 20 * 60), "1 ч 20 мин")
check("сутки", mon.human_duration(26 * 3600), "1 д 2 ч")

print("\nПоказатели Probe")
p = Probe(method="ping", target="t", ok=["Москва", "Казань"], bad=["СПб"], rtt=41)
check("сколько точек всего", p.total, 3)
check("доля доступности", round(p.ratio, 2), 0.67)
check("строка для сообщения", p.short(), "2 из 3, 41 мс")
check("перечисление недоступных", p.bad_list(), "СПб")
check(
    "длинный список обрезается",
    Probe(bad=[f"г{i}" for i in range(9)]).bad_list(limit=3),
    "г0, г1, г2 и ещё 6",
)
check(
    "ошибка проверки видна в тексте",
    Probe(error="пингер недоступен").short(),
    "проверка не выполнена (пингер недоступен)",
)

print("\nОбрезка длинных сообщений для Telegram")
from bot.utils.tg import clamp_html  # noqa: E402

long_text = "\n".join(f"🟢 сервер {i} — <b>ок</b>" for i in range(400))
clamped = clamp_html(long_text)
check("текст влезает в лимит", len(clamped) <= 3900, True)
check("есть пометка об обрезке", "обрезан" in clamped, True)
check("теги не разорваны", clamped.count("<b>") == clamped.count("</b>"), True)
check("короткий текст не трогаем", clamp_html("привет"), "привет")

print("\n" + "─" * 50)
if failed:
    print(f"❌ Провалено {len(failed)} из {passed + len(failed)}:")
    for item in failed:
        print(f"   • {item}")
    sys.exit(1)
print(f"✅ Все проверки пройдены: {passed}")
