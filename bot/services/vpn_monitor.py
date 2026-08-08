"""Мониторинг доступности наших VPN-узлов из России.

Что решаем. Узел может перестать работать по двум совершенно разным
причинам, и реагировать на них надо по-разному:

  • сервер лёг — не отвечает никому, ни в РФ, ни за границей;
  • сервер заблокирован в РФ — за границей отвечает нормально, а из России
    трафик до него не доходит.

Отличить одно от другого одной проверкой нельзя, поэтому цикл двухступенчатый:

  1. Проверяем цель с точек внутри РФ. Если всё хорошо — на этом всё,
     второй запрос не тратим.
  2. Если из РФ не отвечает ни одна точка — делаем контрольную проверку с
     точек за пределами РФ (Казахстан, Бразилия, Индия, ЮАР). Отвечает
     заграница — значит это блокировка в РФ. Не отвечает и она — значит
     лежит сам сервер.

Что проверяем: у всех узлов — TCP-порт 22.

  • IKEv2 (UDP 500/4500) и AmneziaWG (UDP) снаружи не пощупать: у UDP нет
    рукопожатия, «нет ответа» и «дошло, но молчит» выглядят одинаково.
    Поэтому о доступности узла судим по управляющему TCP-порту 22 —
    если до него трафик из РФ не доходит, значит не доходит до сервера.
  • VLESS — тот же TCP 22 по домену сервера.

Порты задаются в .env отдельно для каждого протокола, если однажды
понадобится проверять что-то ещё.

Ложные срабатывания. Единичная неудачная проверка ничего не значит: точка
могла подвиснуть, маршрут — мигнуть. Инцидент открывается только после
MONITOR_FAIL_STREAK подряд неудачных циклов (по умолчанию два, то есть
десять минут). Если пингер сам недоступен, вердикт — «не знаем», и никакие
алерты не уходят: мы не выдумываем аварии из-за проблем измерителя.

Состояние живёт в JSON-файле, поэтому перезапуск бота не теряет открытые
инциденты и не присылает повторных алертов по уже известным авариям.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from bot.config import (
    MONITOR_CONTROL_COUNTRIES,
    MONITOR_CONTROL_POINTS,
    MONITOR_FAIL_STREAK,
    MONITOR_INCLUDE_DISABLED,
    MONITOR_INTERVAL_SEC,
    MONITOR_OK_RATIO,
    MONITOR_OK_STREAK,
    MONITOR_MASS_MIN,
    MONITOR_REMIND_HOURS,
    MONITOR_REPORT_TIME,
    MONITOR_RU_POINTS,
    MONITOR_STATE_FILE,
    MONITOR_TZ_OFFSET,
    MONITOR_AWG_PORTS,
    MONITOR_IKEV2_PORTS,
    MONITOR_VLESS_PORTS,
    MONITOR_VLESS_USE_CONFIG_PORT,
)
from bot.services import geopinger
from bot.services.api_client import api
from bot.utils.format import esc, field as human
from bot.utils.notify import broadcast_admins

log = logging.getLogger(__name__)

# ── Вердикты ────────────────────────────────────────────────────────────────
OK = "ok"
DEGRADED = "degraded"          # часть регионов РФ не видит узел
RU_BLOCKED = "ru_blocked"      # РФ не видит, заграница видит
DOWN = "down"                  # не видит никто
UNKNOWN = "unknown"            # измерить не удалось

VERDICT_ICON = {
    OK: "🟢",
    DEGRADED: "🟠",
    RU_BLOCKED: "🛑",
    DOWN: "🔴",
    UNKNOWN: "⚪️",
}

VERDICT_NAME = {
    OK: "доступен из РФ",
    DEGRADED: "частичная недоступность в РФ",
    RU_BLOCKED: "блокировка в РФ",
    DOWN: "сервер не отвечает",
    UNKNOWN: "нет данных",
}

PROTO_NAME = {
    "ikev2": "🔐 IKEv2",
    "awg": "👽 AWG",
    "vless": "⚡ VLESS",
}

BAD_VERDICTS = (DEGRADED, RU_BLOCKED, DOWN)

_cycle_lock = asyncio.Lock()


# ── Время ───────────────────────────────────────────────────────────────────

def _tz() -> timezone:
    return timezone(timedelta(hours=MONITOR_TZ_OFFSET))


def now_local() -> datetime:
    return datetime.now(_tz())


def fmt_clock(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(ts, _tz()) if ts else now_local()
    return dt.strftime("%H:%M")


def fmt_stamp(ts: float | None = None) -> str:
    dt = datetime.fromtimestamp(ts, _tz()) if ts else now_local()
    return dt.strftime("%d.%m в %H:%M")


def human_duration(seconds: float) -> str:
    seconds = int(max(0, seconds))
    if seconds < 60:
        return f"{seconds} сек"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} мин"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} ч {minutes:02d} мин" if minutes else f"{hours} ч"
    days, hours = divmod(hours, 24)
    return f"{days} д {hours} ч" if hours else f"{days} д"


# ── Цели проверки ───────────────────────────────────────────────────────────

@dataclass
class Target:
    key: str
    proto: str
    label: str
    host: str
    method: str                       # ping | tcp
    ports: list[int] = field(default_factory=list)
    enabled: bool = True
    region: str = ""

    @property
    def title(self) -> str:
        return f"{PROTO_NAME.get(self.proto, self.proto)} · {self.label}"

    @property
    def probe_note(self) -> str:
        if self.method == "ping":
            return "ICMP-пинг"
        return "TCP " + ", ".join(str(p) for p in self.ports)


def _clean(value, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return default if text in ("", "0", "None", "null") else text


def parse_domain_port(value: str) -> tuple[str | None, int | None]:
    """Разбирает поле вида «example.com:8443/path», «example.com» или «8443».

    В базе там встречается всё перечисленное, включая заглушку «0».
    """
    raw = _clean(value)
    if not raw:
        return None, None
    raw = raw.split("/", 1)[0].strip()
    if not raw:
        return None, None
    if raw.isdigit():
        port = int(raw)
        return None, port if 1 <= port <= 65535 else None

    host, _, tail = raw.partition(":")
    host = host.strip() or None
    port = None
    if tail:
        digits = "".join(ch for ch in tail if ch.isdigit())
        if digits:
            candidate = int(digits)
            if 1 <= candidate <= 65535:
                port = candidate
    return host, port


async def collect_targets() -> tuple[list[Target], list[str]]:
    """Собирает актуальный список адресов из основного API.

    Возвращает цели и список замечаний (какой раздел не отдал данные) —
    молчать о том, что часть серверов не проверялась, нельзя.
    """
    targets: list[Target] = []
    issues: list[str] = []

    # ── IKEv2 ──
    data = await api.get("/vpn/api/v1/bot/servers/all")
    if data.get("success") == 1:
        for s in data.get("data") or []:
            ip = _clean(s.get("ipAddress"))
            if not ip:
                continue
            country = human(s.get("country"), "без названия")
            city = _clean(s.get("state"))
            label = f"{country} · {city}" if city else country
            targets.append(Target(
                key=f"ikev2:{ip}",
                proto="ikev2",
                label=label,
                host=ip,
                method="tcp",
                ports=list(MONITOR_IKEV2_PORTS),
                enabled=bool(s.get("status")),
                region=country,
            ))
    else:
        issues.append("список IKEv2 получить не удалось")

    # ── AmneziaWG ──
    data = await api.get("/vpn/api/v1/bot/servers_awg/all")
    if data.get("success") == 1:
        for s in data.get("data") or []:
            ip = _clean(s.get("ip_address"))
            if not ip:
                continue
            country = human(s.get("country"), "без названия")
            city = _clean(s.get("state"))
            label = f"{country} · {city}" if city else country
            targets.append(Target(
                key=f"awg:{ip}",
                proto="awg",
                label=label,
                host=ip,
                method="tcp",
                ports=list(MONITOR_AWG_PORTS),
                enabled=bool(s.get("status")),
                region=country,
            ))
    else:
        issues.append("список AWG получить не удалось")

    # ── VLESS ──
    data = await api.get("/vpn/api/v1/bot/servers_vless/all")
    if data.get("success") == 1:
        for s in data.get("data") or []:
            host = _clean(s.get("server_ip"))
            cfg_host, cfg_port = parse_domain_port(s.get("server_domain_port_path"))
            host = host or cfg_host
            if not host:
                continue
            ports = list(MONITOR_VLESS_PORTS)
            if MONITOR_VLESS_USE_CONFIG_PORT and cfg_port and cfg_port not in ports:
                ports.append(cfg_port)
            targets.append(Target(
                key=f"vless:{host}",
                proto="vless",
                label=human(s.get("description"), host),
                host=host,
                method="tcp",
                ports=ports,
                enabled=True,          # у VLESS в базе нет флага включения
                region="",
            ))
    else:
        issues.append("список VLESS получить не удалось")

    return targets, issues


# ── Состояние ───────────────────────────────────────────────────────────────

def _empty_state() -> dict:
    return {
        "version": 1,
        "muted_until": 0,
        "targets": {},
        "day": {"date": "", "cycles": 0, "probes": 0, "incidents": []},
        "last_report_date": "",
        "last_cycle": 0,
        "pinger_ok": True,
        "pinger_reason": "",
    }


_state: dict | None = None


def state() -> dict:
    global _state
    if _state is None:
        try:
            with open(MONITOR_STATE_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            base = _empty_state()
            base.update(loaded if isinstance(loaded, dict) else {})
            _state = base
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            _state = _empty_state()
    return _state


def save_state() -> None:
    data = state()
    try:
        tmp = f"{MONITOR_STATE_FILE}.tmp"
        os.makedirs(os.path.dirname(os.path.abspath(MONITOR_STATE_FILE)), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, MONITOR_STATE_FILE)
    except OSError as e:
        log.warning("Не удалось сохранить состояние мониторинга: %s", e)


def _target_state(key: str) -> dict:
    targets = state().setdefault("targets", {})
    return targets.setdefault(key, {
        "verdict": UNKNOWN,
        "fail_streak": 0,
        "ok_streak": 0,
        "last_check": 0,
        "ru": "",
        "ru_ratio": 0.0,
        "rtt": None,
        "bad_points": [],
        "control": "",
        "incident": None,
        "label": "",
        "proto": "",
        "checks": 0,
        "fails": 0,
    })


def _day_bucket() -> dict:
    day = state().setdefault("day", {"date": "", "cycles": 0, "probes": 0, "incidents": []})
    today = now_local().strftime("%Y-%m-%d")
    if day.get("date") != today:
        day.clear()
        day.update({"date": today, "cycles": 0, "probes": 0, "incidents": []})
    return day


def is_muted() -> bool:
    return time.time() < float(state().get("muted_until") or 0)


def mute_for(minutes: int) -> None:
    state()["muted_until"] = time.time() + minutes * 60 if minutes > 0 else 0
    save_state()


# ── Логика вердикта (чистая, покрыта тестами) ───────────────────────────────

def classify(ru: geopinger.Probe, control: geopinger.Probe | None, ok_ratio: float = None) -> str:
    """Вердикт по результатам проверок. Без побочных эффектов."""
    threshold = MONITOR_OK_RATIO if ok_ratio is None else ok_ratio

    if not ru.usable:
        return UNKNOWN
    if ru.ratio >= threshold:
        return OK
    if ru.ratio > 0:
        return DEGRADED

    # Из РФ не отвечает ни одна точка — смотрим контроль.
    if control is None or not control.usable:
        return DOWN
    return RU_BLOCKED if control.ratio > 0 else DOWN


async def check_target(target: Target) -> tuple[str, geopinger.Probe, geopinger.Probe | None]:
    """Проверяет одну цель: РФ, при полном отказе — контроль из-за рубежа."""
    if target.method == "ping":
        ru = await geopinger.ping(target.host, countries=["ru"], limit=MONITOR_RU_POINTS)
    else:
        ru = await geopinger.tcp(target.host, target.ports, countries=["ru"], limit=MONITOR_RU_POINTS)

    control: geopinger.Probe | None = None
    if ru.usable and ru.ratio == 0:
        if target.method == "ping":
            control = await geopinger.ping(
                target.host, countries=MONITOR_CONTROL_COUNTRIES, limit=MONITOR_CONTROL_POINTS
            )
        else:
            control = await geopinger.tcp(
                target.host, target.ports,
                countries=MONITOR_CONTROL_COUNTRIES, limit=MONITOR_CONTROL_POINTS,
            )

    return classify(ru, control), ru, control


# ── Тексты сообщений ────────────────────────────────────────────────────────

def _where_line(ru: geopinger.Probe, control: geopinger.Probe | None) -> str:
    lines = [f"Из РФ: {ru.short()}."]
    if ru.bad:
        lines.append(f"Не отвечает: {ru.bad_list()}.")
    if control is not None:
        if control.usable:
            lines.append(f"Из-за рубежа: {control.short()}.")
        else:
            lines.append(f"Контрольная проверка из-за рубежа: {control.error}.")
    return "\n".join(lines)


def _verdict_comment(verdict: str, control: geopinger.Probe | None) -> str:
    if verdict == RU_BLOCKED:
        return "Сервер живой, но из России до него не доходят — похоже на блокировку."
    if verdict == DOWN:
        if control is None or not control.usable:
            return (
                "Из РФ не отвечает ни одна точка. Подтвердить заграницей не получилось, "
                "поэтому причину пока не разделяем: возможен и сбой сервера, и блокировка."
            )
        return "Не отвечает ни из РФ, ни из-за рубежа — похоже, лежит сам сервер."
    if verdict == DEGRADED:
        return "Часть регионов РФ сервер не видит. Так обычно начинается блокировка у отдельных операторов."
    return ""


def alert_text(target_title: str, host: str, probe_note: str, verdict: str,
               ru: geopinger.Probe, control: geopinger.Probe | None) -> str:
    head = {
        RU_BLOCKED: "🛑 <b>Сервер недоступен из РФ</b>",
        DOWN: "🔴 <b>Сервер не отвечает</b>",
        DEGRADED: "🟠 <b>Частичная недоступность в РФ</b>",
    }.get(verdict, "⚠️ <b>Проблема с сервером</b>")

    return (
        f"{head}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{esc(target_title)}\n"
        f"🌐 <code>{esc(host)}</code> · {esc(probe_note)}\n"
        f"🕒 {fmt_stamp()} (МСК)\n\n"
        f"{esc(_where_line(ru, control))}\n\n"
        f"{esc(_verdict_comment(verdict, control))}\n"
        f"Продолжаем проверять каждые 5 минут — о восстановлении сообщим."
    )


def change_text(target_title: str, host: str, was: str, now: str,
                ru: geopinger.Probe, control: geopinger.Probe | None, since: float) -> str:
    return (
        f"🔁 <b>Изменился характер проблемы</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{esc(target_title)}\n"
        f"🌐 <code>{esc(host)}</code>\n"
        f"Было: {esc(VERDICT_NAME.get(was, was))} → стало: <b>{esc(VERDICT_NAME.get(now, now))}</b>\n"
        f"🕒 {fmt_stamp()} (МСК) · проблема тянется {esc(human_duration(time.time() - since))}\n\n"
        f"{esc(_where_line(ru, control))}"
    )


def recovery_text(target_title: str, host: str, kind: str, started_at: float,
                  ru: geopinger.Probe) -> str:
    return (
        f"🟢 <b>Сервер снова доступен из РФ</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{esc(target_title)}\n"
        f"🌐 <code>{esc(host)}</code>\n"
        f"🕒 {fmt_stamp()} (МСК)\n"
        f"⏳ Не работал {esc(human_duration(time.time() - started_at))} "
        f"(с {esc(fmt_stamp(started_at))})\n"
        f"📉 Причина по нашим замерам: {esc(VERDICT_NAME.get(kind, kind))}\n\n"
        f"Сейчас из РФ: {esc(ru.short())}."
    )


def remind_text(items: list[tuple[str, str, float]]) -> str:
    lines = [
        "⏰ <b>Напоминание: проблемы не решены</b>",
        "━━━━━━━━━━━━━━━",
    ]
    for title, kind, started in items:
        lines.append(
            f"{VERDICT_ICON.get(kind, '⚠️')} {esc(title)} — {esc(VERDICT_NAME.get(kind, kind))}, "
            f"уже {esc(human_duration(time.time() - started))}"
        )
    lines.append(f"\n🕒 {fmt_stamp()} (МСК)")
    return "\n".join(lines)


def mass_text(items: list[tuple[str, str, str]]) -> str:
    lines = [
        "🚨 <b>Массовый сбой</b>",
        "━━━━━━━━━━━━━━━",
        f"Разом отвалилось серверов: <b>{len(items)}</b>. Список:",
        "",
    ]
    for title, host, kind in items:
        lines.append(f"{VERDICT_ICON.get(kind, '⚠️')} {esc(title)} — {esc(VERDICT_NAME.get(kind, kind))}")
    lines.append("")
    lines.append(f"🕒 {fmt_stamp()} (МСК)")
    lines.append(
        "Столько узлов сразу редко падает само — проверьте сеть, "
        "провайдера и наш основной API, прежде чем чинить каждый сервер."
    )
    return "\n".join(lines)


# ── Цикл проверки ───────────────────────────────────────────────────────────

async def run_cycle(bot, notify: bool = True) -> dict:
    """Один полный проход по всем адресам.

    notify=False — проверить без рассылки (используется кнопкой «Проверить
    сейчас», чтобы админ не получал дубли того, что видит на экране).
    """
    if _cycle_lock.locked():
        log.info("Предыдущий цикл ещё идёт — пропускаем этот запуск")
        return {"skipped": True}

    async with _cycle_lock:
        started = time.time()
        st = state()
        day = _day_bucket()

        targets, issues = await collect_targets()
        active = [t for t in targets if t.enabled or MONITOR_INCLUDE_DISABLED]
        skipped = len(targets) - len(active)

        # Убираем из состояния то, что удалили из панели.
        alive_keys = {t.key for t in targets}
        for key in list(st.get("targets", {})):
            if key not in alive_keys:
                st["targets"].pop(key, None)

        opened: list[tuple[str, str, str]] = []   # (title, host, kind)
        messages: list[str] = []
        summary = {v: 0 for v in (OK, DEGRADED, RU_BLOCKED, DOWN, UNKNOWN)}
        pinger_fail = 0

        for target in active:
            try:
                verdict, ru, control = await check_target(target)
            except Exception as e:  # noqa: BLE001 — один сервер не должен рушить цикл
                log.exception("Проверка %s сорвалась: %s", target.key, e)
                continue

            day["probes"] = day.get("probes", 0) + (2 if control is not None else 1)
            summary[verdict] = summary.get(verdict, 0) + 1
            if verdict == UNKNOWN:
                pinger_fail += 1

            ts = _target_state(target.key)
            ts.update({
                "label": target.title,
                "proto": target.proto,
                "host": target.host,
                "probe": target.probe_note,
                "last_check": time.time(),
                "ru": ru.short(),
                "ru_ratio": round(ru.ratio, 3),
                "rtt": ru.rtt,
                "bad_points": ru.bad[:10],
                "control": control.short() if control is not None else "",
                "checks": ts.get("checks", 0) + 1,
            })

            # Вердикт «не знаем» не двигает счётчики: измеритель подвёл,
            # а не сервер.
            if verdict == UNKNOWN:
                ts["verdict"] = UNKNOWN
                continue

            if verdict == OK:
                ts["fail_streak"] = 0
                ts["ok_streak"] = ts.get("ok_streak", 0) + 1
                incident = ts.get("incident")
                if incident and ts["ok_streak"] >= MONITOR_OK_STREAK:
                    duration = time.time() - incident["started_at"]
                    day.setdefault("incidents", []).append({
                        "title": target.title,
                        "proto": target.proto,
                        "kind": incident.get("peak_kind", incident["kind"]),
                        "started_at": incident["started_at"],
                        "ended_at": time.time(),
                        "duration": duration,
                    })
                    if incident.get("notified"):
                        messages.append(recovery_text(
                            target.title, target.host,
                            incident.get("peak_kind", incident["kind"]),
                            incident["started_at"], ru,
                        ))
                    ts["incident"] = None
                ts["verdict"] = OK
                continue

            # Проблемный вердикт
            ts["ok_streak"] = 0
            ts["fail_streak"] = ts.get("fail_streak", 0) + 1
            ts["fails"] = ts.get("fails", 0) + 1
            ts["verdict"] = verdict

            incident = ts.get("incident")
            if incident is None:
                if ts["fail_streak"] < MONITOR_FAIL_STREAK:
                    # Ещё не уверены — молчим, ждём следующий цикл.
                    continue
                incident = {
                    "kind": verdict,
                    "peak_kind": verdict,
                    # Проблема началась не сейчас, а на первом неудачном цикле —
                    # иначе длительность простоя в отчёте будет занижена.
                    "started_at": time.time() - (ts["fail_streak"] - 1) * MONITOR_INTERVAL_SEC,
                    "notified": False,
                    "last_remind": time.time(),
                }
                ts["incident"] = incident
                opened.append((target.title, target.host, verdict))
                incident["notified"] = True
                messages.append(alert_text(
                    target.title, target.host, target.probe_note, verdict, ru, control,
                ))
            else:
                previous = incident.get("kind")
                if previous != verdict:
                    # Деградация переросла в блокировку или наоборот — это
                    # новая информация, о ней сообщаем.
                    order = {DEGRADED: 1, RU_BLOCKED: 2, DOWN: 3}
                    if order.get(verdict, 0) > order.get(incident.get("peak_kind"), 0):
                        incident["peak_kind"] = verdict
                    incident["kind"] = verdict
                    if incident.get("notified"):
                        messages.append(change_text(
                            target.title, target.host, previous, verdict,
                            ru, control, incident["started_at"],
                        ))

        # ── Здоровье самого пингера ──
        if active and pinger_fail == len(active):
            if st.get("pinger_ok", True):
                st["pinger_ok"] = False
                st["pinger_reason"] = "ни одна проверка не выполнилась"
                messages.insert(0, (
                    "⚪️ <b>Пингер не отвечает</b>\n"
                    "━━━━━━━━━━━━━━━\n"
                    f"🕒 {fmt_stamp()} (МСК)\n\n"
                    "Проверки доступности сейчас не выполняются, состояние серверов неизвестно. "
                    "Пока пингер молчит, алертов о блокировках не будет — "
                    "чтобы не выдумывать аварии на пустом месте."
                ))
        elif not st.get("pinger_ok", True):
            st["pinger_ok"] = True
            st["pinger_reason"] = ""
            messages.insert(0, (
                "⚪️➡️🟢 <b>Пингер снова отвечает</b>\n"
                f"🕒 {fmt_stamp()} (МСК)\n"
                "Мониторинг доступности продолжается в обычном режиме."
            ))

        # ── Напоминания по затянувшимся инцидентам ──
        if MONITOR_REMIND_HOURS > 0:
            due: list[tuple[str, str, float]] = []
            for key, ts in st.get("targets", {}).items():
                incident = ts.get("incident")
                if not incident or not incident.get("notified"):
                    continue
                last = incident.get("last_remind") or incident["started_at"]
                if time.time() - last >= MONITOR_REMIND_HOURS * 3600:
                    incident["last_remind"] = time.time()
                    due.append((ts.get("label", key), incident["kind"], incident["started_at"]))
            if due:
                messages.append(remind_text(due))

        day["cycles"] = day.get("cycles", 0) + 1
        st["last_cycle"] = time.time()
        st["last_duration"] = round(time.time() - started, 1)
        st["last_summary"] = summary
        st["last_issues"] = issues
        st["last_skipped"] = skipped
        save_state()

        # ── Рассылка ──
        if notify and not is_muted():
            # Массовая авария — одно сообщение вместо десятков.
            if len(opened) >= max(MONITOR_MASS_MIN, 2) and len(opened) >= len(active) / 2:
                await broadcast_admins(bot, mass_text(opened))
                # Оставляем только то, что не относится к массовому падению.
                keep = [m for m in messages if not m.startswith(("🛑", "🔴", "🟠"))]
                messages = keep
            for text in messages:
                await broadcast_admins(bot, text)

        return {
            "skipped": False,
            "targets": len(active),
            "summary": summary,
            "issues": issues,
            "duration": round(time.time() - started, 1),
            "opened": opened,
            "muted": is_muted(),
        }


# ── Ежедневная сводка ───────────────────────────────────────────────────────

def build_daily_report(for_date: str | None = None) -> str:
    st = state()
    day = _day_bucket()
    date_label = now_local().strftime("%d.%m.%Y") if not for_date else for_date

    summary = st.get("last_summary") or {}
    by_proto: dict[str, int] = {}
    open_items: list[tuple[str, str, float]] = []
    for key, ts in (st.get("targets") or {}).items():
        by_proto[ts.get("proto", "?")] = by_proto.get(ts.get("proto", "?"), 0) + 1
        incident = ts.get("incident")
        if incident:
            open_items.append((ts.get("label", key), incident["kind"], incident["started_at"]))

    total = sum(by_proto.values())
    proto_part = " · ".join(
        f"{PROTO_NAME.get(p, p)} {c}" for p, c in sorted(by_proto.items()) if c
    )

    lines = [
        f"📋 <b>Сводка за {esc(date_label)}</b>",
        "━━━━━━━━━━━━━━━",
        f"🖥 Под наблюдением: <b>{total}</b>" + (f"\n{esc(proto_part)}" if proto_part else ""),
        f"🔄 Циклов проверки: <b>{day.get('cycles', 0)}</b> · замеров: <b>{day.get('probes', 0)}</b>",
    ]

    if st.get("last_skipped"):
        lines.append(f"⏸ Выключенных серверов пропущено: {st['last_skipped']}")
    if not st.get("pinger_ok", True):
        lines.append("⚠️ Пингер сейчас недоступен — последние данные могут быть устаревшими")
    for issue in st.get("last_issues") or []:
        lines.append(f"⚠️ {esc(issue)}")

    closed = day.get("incidents") or []
    lines.append("")

    if not closed and not open_items:
        lines.append("✅ Аномалий за сутки нет. Все адреса всё время отвечали из РФ.")
    else:
        if closed:
            lines.append(f"📉 <b>Отработавшие события: {len(closed)}</b>")
            for item in sorted(closed, key=lambda x: x["started_at"]):
                lines.append(
                    f"• {esc(fmt_clock(item['started_at']))}–{esc(fmt_clock(item['ended_at']))} "
                    f"({esc(human_duration(item['duration']))}) — {esc(item['title'])} — "
                    f"{esc(VERDICT_NAME.get(item['kind'], item['kind']))}"
                )
            worst = max(closed, key=lambda x: x["duration"])
            lines.append(
                f"\nСамый долгий простой: {esc(worst['title'])} — "
                f"{esc(human_duration(worst['duration']))}."
            )
        if open_items:
            lines.append("")
            lines.append(f"🔴 <b>Не работают прямо сейчас: {len(open_items)}</b>")
            for title, kind, started in sorted(open_items, key=lambda x: x[2]):
                lines.append(
                    f"• {VERDICT_ICON.get(kind, '⚠️')} {esc(title)} — "
                    f"{esc(VERDICT_NAME.get(kind, kind))}, уже "
                    f"{esc(human_duration(time.time() - started))}"
                )

    if is_muted():
        until = fmt_clock(state().get("muted_until"))
        lines.append(f"\n🔇 Уведомления приглушены до {esc(until)} (МСК).")

    lines.append(f"\n🕒 Отчёт собран в {fmt_clock()} (МСК).")
    return "\n".join(lines)


def report_due() -> bool:
    """Пора ли отправлять суточную сводку.

    Проверяем по локальной дате, а не по таймеру планировщика: если бот
    перезапускали, отчёт всё равно уйдёт один раз и в нужный день.
    """
    try:
        hour, minute = (int(x) for x in MONITOR_REPORT_TIME.split(":", 1))
    except (ValueError, AttributeError):
        hour, minute = 23, 50

    now = now_local()
    today = now.strftime("%Y-%m-%d")
    if state().get("last_report_date") == today:
        return False
    return (now.hour, now.minute) >= (hour, minute)


def mark_report_sent() -> None:
    state()["last_report_date"] = now_local().strftime("%Y-%m-%d")
    save_state()


# ── Взгляд на текущее состояние (для админ-меню) ────────────────────────────

def status_snapshot() -> dict:
    st = state()
    items = []
    for key, ts in (st.get("targets") or {}).items():
        items.append({
            "key": key,
            "label": ts.get("label", key),
            "proto": ts.get("proto", ""),
            "host": ts.get("host", ""),
            "verdict": ts.get("verdict", UNKNOWN),
            "ru": ts.get("ru", ""),
            "ru_ratio": ts.get("ru_ratio", 0),
            "rtt": ts.get("rtt"),
            "bad_points": ts.get("bad_points") or [],
            "control": ts.get("control", ""),
            "incident": ts.get("incident"),
            "last_check": ts.get("last_check", 0),
            "probe": ts.get("probe", ""),
        })

    order = {RU_BLOCKED: 0, DOWN: 1, DEGRADED: 2, UNKNOWN: 3, OK: 4}
    items.sort(key=lambda x: (order.get(x["verdict"], 9), x["label"]))

    return {
        "items": items,
        "last_cycle": st.get("last_cycle", 0),
        "last_duration": st.get("last_duration"),
        "muted_until": st.get("muted_until", 0),
        "pinger_ok": st.get("pinger_ok", True),
        "issues": st.get("last_issues") or [],
        "skipped": st.get("last_skipped", 0),
    }
