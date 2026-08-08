"""Клиент GEOPinger API — проверка наших узлов с точек в разных странах.

Сервис синхронный: один POST — один готовый результат, внутри он сам ждёт
задачу на geopinger.net. Поэтому здесь нет опроса статусов, только запрос,
разбор ответа и аккуратная обработка отказов.

Ответ приходит в виде «город → результат», причём города, которые не
ответили, в выдачу вообще не попадают. Отсюда важное следствие: доступность
считаем от числа реально ответивших точек (points_count), а не от того,
сколько мы просили.

Документация живого сервиса: <GEOPINGER_URL>/docs и /llms.txt
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import httpx

from bot.config import (
    GEOPINGER_API_KEY,
    GEOPINGER_CONCURRENCY,
    GEOPINGER_TIMEOUT,
    GEOPINGER_URL,
)

log = logging.getLogger(__name__)

# Таймаут одной проверки на стороне пингера — до 45 секунд (DPI).
# Клиентский таймаут держим заметно больше, иначе будем рвать нормальные
# проверки и считать живые серверы мёртвыми.
_sem: asyncio.Semaphore | None = None
_client: httpx.AsyncClient | None = None


def _semaphore() -> asyncio.Semaphore:
    """Ограничитель параллелизма, создаётся внутри работающего loop."""
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(max(1, GEOPINGER_CONCURRENCY))
    return _sem


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        headers = {"Content-Type": "application/json"}
        if GEOPINGER_API_KEY:
            headers["X-API-Key"] = GEOPINGER_API_KEY
        _client = httpx.AsyncClient(timeout=GEOPINGER_TIMEOUT, headers=headers)
    return _client


async def aclose() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


@dataclass
class Probe:
    """Итог одной проверки цели с группы точек.

    ok   — города, из которых цель доступна;
    bad  — города, из которых недоступна;
    note — короткая причина по городу («порт 22 закрыт», «потери 3/3»);
    rtt  — средний отклик по доступным точкам, мс;
    error — заполнено, если проверка вообще не состоялась (пингер молчит,
            неверный ключ и т.п.). В этом случае выводы делать нельзя.
    """

    method: str = ""
    target: str = ""
    ok: list[str] = field(default_factory=list)
    bad: list[str] = field(default_factory=list)
    note: dict[str, str] = field(default_factory=dict)
    rtt: int | None = None
    error: str | None = None
    partial: bool = False

    @property
    def total(self) -> int:
        return len(self.ok) + len(self.bad)

    @property
    def usable(self) -> bool:
        """Есть ли на что опираться: без ошибки и хотя бы одна точка ответила."""
        return self.error is None and self.total > 0

    @property
    def ratio(self) -> float:
        return len(self.ok) / self.total if self.total else 0.0

    def short(self) -> str:
        """Строчка для сообщения: «4 из 6 точек, 41 мс»."""
        if self.error:
            return f"проверка не выполнена ({self.error})"
        if not self.total:
            return "ни одна точка не ответила"
        base = f"{len(self.ok)} из {self.total}"
        if self.rtt is not None and self.ok:
            base += f", {self.rtt} мс"
        return base

    def bad_list(self, limit: int = 6) -> str:
        """Перечисление городов, откуда цель не достаётся."""
        if not self.bad:
            return "—"
        shown = self.bad[:limit]
        tail = f" и ещё {len(self.bad) - limit}" if len(self.bad) > limit else ""
        return ", ".join(shown) + tail


def _payload(target: str, countries: list[str] | None, limit: int | None, **extra) -> dict:
    body: dict = {"target": target}
    if countries:
        body["countries"] = countries
    if limit:
        body["limit"] = int(limit)
    body.update(extra)
    return body


async def _request(path: str, body: dict) -> tuple[dict | None, str | None]:
    """POST к пингеру с одним повтором. Возвращает (данные, причина отказа)."""
    if not GEOPINGER_URL:
        return None, "адрес пингера не задан"

    url = f"{GEOPINGER_URL}{path}"
    reason = "нет ответа"

    for attempt in (1, 2):
        try:
            async with _semaphore():
                resp = await _http().post(url, json=body)

            if resp.status_code == 200:
                try:
                    return resp.json(), None
                except ValueError:
                    reason = "пингер вернул не JSON"
            elif resp.status_code in (401, 403):
                return None, "пингер не принял ключ доступа"
            elif resp.status_code == 429:
                reason = "пингер ограничил частоту запросов"
            elif resp.status_code >= 500:
                reason = f"пингер ответил {resp.status_code}"
            else:
                reason = f"пингер ответил {resp.status_code}"

        except httpx.TimeoutException:
            reason = "пингер не ответил за отведённое время"
        except httpx.ConnectError:
            reason = "пингер недоступен"
        except Exception as e:  # noqa: BLE001 — в мониторинге важнее не упасть
            reason = f"{type(e).__name__}"
            log.warning("Запрос к пингеру сорвался: %s: %s", type(e).__name__, e)

        if attempt == 1:
            await asyncio.sleep(3)

    return None, reason


def _finish(probe: Probe, data: dict, rtts: list[float]) -> Probe:
    probe.partial = not bool(data.get("finished", True))
    if rtts:
        probe.rtt = int(round(sum(rtts) / len(rtts)))
    return probe


async def ping(target: str, countries: list[str] | None = None, limit: int | None = None) -> Probe:
    """ICMP-пинг цели со всех выбранных точек."""
    probe = Probe(method="ping", target=target)
    data, err = await _request("/api/v1/ping", _payload(target, countries, limit))
    if err or data is None:
        probe.error = err or "нет ответа"
        return probe

    rtts: list[float] = []
    for city, res in (data.get("results") or {}).items():
        if not isinstance(res, dict):
            continue
        sent = int(res.get("sent") or 0)
        lost = int(res.get("lost") or 0)
        alive = bool(res.get("ping")) and not (sent and lost >= sent)
        if alive:
            probe.ok.append(city)
            rtt = res.get("rtt_avg") or res.get("rtt")
            if isinstance(rtt, (int, float)) and rtt > 0:
                rtts.append(float(rtt))
        else:
            probe.bad.append(city)
            probe.note[city] = f"потери {lost}/{sent}" if sent else "нет ответа"

    return _finish(probe, data, rtts)


async def tcp(
    target: str,
    ports: list[int],
    countries: list[str] | None = None,
    limit: int | None = None,
) -> Probe:
    """Проверка TCP-портов цели.

    Точка считается «видит сервер», если хотя бы один из запрошенных портов
    принял соединение: для VPN-узла этого достаточно, чтобы утверждать, что
    трафик до него доходит.
    """
    probe = Probe(method="tcp", target=target)
    ports = [int(p) for p in ports if p]
    if not ports:
        probe.error = "не заданы порты для проверки"
        return probe

    data, err = await _request("/api/v1/tcp", _payload(target, countries, limit, ports=ports))
    if err or data is None:
        probe.error = err or "нет ответа"
        return probe

    rtts: list[float] = []
    for city, res in (data.get("results") or {}).items():
        if not isinstance(res, dict):
            continue

        opened: list[int] = []
        closed: list[int] = []
        timed_out = False
        for port in ports:
            item = res.get(str(port))
            if not isinstance(item, dict):
                continue
            if item.get("success"):
                opened.append(port)
                latency = item.get("latency")
                if isinstance(latency, (int, float)) and latency > 0:
                    rtts.append(float(latency))
            else:
                closed.append(port)
                if isinstance(item.get("latency"), (int, float)) and item["latency"] >= 5000:
                    timed_out = True

        if opened:
            probe.ok.append(city)
        else:
            probe.bad.append(city)
            if not closed:
                probe.note[city] = "точка не вернула данные по портам"
            elif timed_out:
                probe.note[city] = f"таймаут на {', '.join(str(p) for p in closed)}"
            else:
                probe.note[city] = f"порт {', '.join(str(p) for p in closed)} закрыт"

    return _finish(probe, data, rtts)


async def health() -> tuple[bool, str]:
    """Живость самого пингера — для диагностики и статус-борда."""
    if not GEOPINGER_URL:
        return False, "адрес пингера не задан"
    try:
        resp = await _http().get(f"{GEOPINGER_URL}/health", timeout=15.0)
        if resp.status_code == 200:
            return True, "отвечает"
        return False, f"ответил {resp.status_code}"
    except httpx.TimeoutException:
        return False, "не ответил за 15 с"
    except Exception as e:  # noqa: BLE001
        return False, type(e).__name__


async def points_countries() -> tuple[list[str], str | None]:
    """Список стран, по которым у пингера есть точки."""
    if not GEOPINGER_URL:
        return [], "адрес пингера не задан"
    try:
        resp = await _http().get(f"{GEOPINGER_URL}/api/v1/points/countries", timeout=20.0)
        if resp.status_code != 200:
            return [], f"пингер ответил {resp.status_code}"
        data = resp.json()
        if isinstance(data, dict):
            raw = data.get("countries") or data.get("data") or []
        else:
            raw = data
        out: list[str] = []
        for item in raw or []:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                code = item.get("code") or item.get("country") or item.get("id")
                if code:
                    out.append(str(code))
        return out, None
    except Exception as e:  # noqa: BLE001
        return [], type(e).__name__
