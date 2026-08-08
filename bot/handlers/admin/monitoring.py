"""Раздел «Доступность из РФ» в админке бота.

Экраны: общий борд по всем адресам, карточка отдельного сервера с разбивкой
по городам, список событий за сутки, ручная проверка и режим тишины.
"""
from __future__ import annotations

import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.config import (
    GEOPINGER_URL,
    MONITOR_CONTROL_COUNTRIES,
    MONITOR_ENABLED,
    MONITOR_FAIL_STREAK,
    MONITOR_INTERVAL_SEC,
    MONITOR_REPORT_TIME,
    MONITOR_RU_POINTS,
)
from bot.services import geopinger, vpn_monitor as mon
from bot.utils.auth import admin_only
from bot.utils.format import esc, sid, resolve_sid
from bot.utils.tg import safe_edit_query

BACK = "monitor:home"


def _not_configured_text() -> str:
    return (
        "📡 <b>Доступность из РФ</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "Модуль не настроен: не задан адрес пингера.\n\n"
        "Добавьте в <code>bot/.env</code> строки:\n"
        "<code>GEOPINGER_URL=http://адрес:8080</code>\n"
        "<code>GEOPINGER_API_KEY=ваш_ключ</code>\n\n"
        "После этого перезапустите бота."
    )


def home_kb() -> InlineKeyboardMarkup:
    muted = mon.is_muted()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗺 Состояние серверов", callback_data="monitor:board")],
        [InlineKeyboardButton("📉 События за сутки", callback_data="monitor:events")],
        [InlineKeyboardButton("🔄 Проверить сейчас", callback_data="monitor:check")],
        [InlineKeyboardButton("📋 Сводка за сегодня", callback_data="monitor:report")],
        [InlineKeyboardButton(
            "🔔 Включить уведомления" if muted else "🔇 Приглушить уведомления",
            callback_data="monitor:unmute" if muted else "monitor:mute",
        )],
        [InlineKeyboardButton("🩺 Проверить пингер", callback_data="monitor:selftest")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")],
    ])


def _age(ts: float) -> str:
    if not ts:
        return "проверок ещё не было"
    return f"{mon.human_duration(time.time() - ts)} назад"


def home_text() -> str:
    snap = mon.status_snapshot()
    items = snap["items"]
    counts: dict[str, int] = {}
    for item in items:
        counts[item["verdict"]] = counts.get(item["verdict"], 0) + 1

    bad = sum(counts.get(v, 0) for v in mon.BAD_VERDICTS)
    if not items:
        headline = "Данных ещё нет — первая проверка вот-вот пройдёт."
    elif bad == 0:
        headline = f"Всё в порядке: {counts.get(mon.OK, 0)} адресов отвечают из РФ."
    else:
        headline = f"Проблемных адресов: <b>{bad}</b> из {len(items)}."

    lines = [
        "📡 <b>Доступность из РФ</b>",
        "━━━━━━━━━━━━━━━",
        headline,
        "",
        f"🟢 норма: {counts.get(mon.OK, 0)} · 🟠 частично: {counts.get(mon.DEGRADED, 0)} · "
        f"🛑 блокировка: {counts.get(mon.RU_BLOCKED, 0)} · 🔴 не отвечает: {counts.get(mon.DOWN, 0)}"
        + (f" · ⚪️ нет данных: {counts[mon.UNKNOWN]}" if counts.get(mon.UNKNOWN) else ""),
        "",
        f"🕒 Последний обход: {esc(_age(snap['last_cycle']))}"
        + (f", занял {snap['last_duration']} с" if snap.get("last_duration") else ""),
        f"⏱ Интервал: раз в {MONITOR_INTERVAL_SEC // 60} мин · "
        f"точек в РФ: {MONITOR_RU_POINTS} · контроль: {esc(', '.join(MONITOR_CONTROL_COUNTRIES).upper())}",
        f"📋 Суточная сводка: в {esc(MONITOR_REPORT_TIME)} (МСК)",
    ]

    if not snap["pinger_ok"]:
        lines.append("\n⚠️ Пингер не отвечает — проверки сейчас не идут.")
    if snap.get("skipped"):
        lines.append(f"⏸ Выключенных серверов пропускаем: {snap['skipped']}")
    for issue in snap["issues"]:
        lines.append(f"⚠️ {esc(issue)}")
    if mon.is_muted():
        lines.append(f"\n🔇 Уведомления приглушены до {esc(mon.fmt_clock(snap['muted_until']))} (МСК).")

    return "\n".join(lines)


@admin_only
async def monitor_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("auto_update_view", None)
    if not GEOPINGER_URL or not MONITOR_ENABLED:
        await safe_edit_query(
            query, _not_configured_text(),
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="menu:main")]]),
        )
        return
    await safe_edit_query(query, home_text(), home_kb())


@admin_only
async def monitor_board(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    snap = mon.status_snapshot()
    items = snap["items"]

    if not items:
        await safe_edit_query(
            query,
            "🗺 <b>Состояние серверов</b>\n━━━━━━━━━━━━━━━\n"
            "Проверок ещё не было. Нажмите «Проверить сейчас» или подождите ближайший обход.",
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=BACK)]]),
        )
        return

    lines = ["🗺 <b>Состояние серверов</b>", "━━━━━━━━━━━━━━━"]
    keyboard = []
    for item in items:
        icon = mon.VERDICT_ICON.get(item["verdict"], "⚪️")
        detail = item["ru"] or "нет данных"
        extra = ""
        if item["incident"]:
            extra = f" · уже {mon.human_duration(time.time() - item['incident']['started_at'])}"
        lines.append(f"{icon} {esc(item['label'])} — {esc(detail)}{esc(extra)}")
        # Кнопки заводим только на проблемные адреса и не больше десяти:
        # Telegram ограничивает размер клавиатуры, а список может быть длинным.
        if item["verdict"] in mon.BAD_VERDICTS and len(keyboard) < 10:
            keyboard.append([InlineKeyboardButton(
                f"{icon} {item['label'][:40]}",
                callback_data=f"monitor:t:{sid(item['key'])}",
            )])

    lines.append("")
    lines.append(f"🕒 Обновлено: {esc(_age(snap['last_cycle']))}")
    if keyboard:
        lines.append("Нажмите на проблемный сервер, чтобы увидеть детали.")

    keyboard.append([
        InlineKeyboardButton("🔄 Обновить", callback_data="monitor:board"),
        InlineKeyboardButton("⬅️ Назад", callback_data=BACK),
    ])
    await safe_edit_query(query, "\n".join(lines), InlineKeyboardMarkup(keyboard))


@admin_only
async def monitor_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_sid = query.data.split(":")[-1]
    snap = mon.status_snapshot()
    key = resolve_sid(target_sid, [i["key"] for i in snap["items"]])
    item = next((i for i in snap["items"] if i["key"] == key), None)

    if item is None:
        await safe_edit_query(
            query, "❌ Сервер больше не в списке — возможно, его удалили из панели.",
            InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ К списку", callback_data="monitor:board")]]),
        )
        return

    icon = mon.VERDICT_ICON.get(item["verdict"], "⚪️")
    lines = [
        f"{icon} <b>{esc(item['label'])}</b>",
        "━━━━━━━━━━━━━━━",
        f"🌐 Адрес: <code>{esc(item['host'])}</code>",
        f"🔎 Как проверяем: {esc(item['probe'])}",
        f"📶 Вердикт: <b>{esc(mon.VERDICT_NAME.get(item['verdict'], item['verdict']))}</b>",
        f"🇷🇺 Из РФ: {esc(item['ru'] or 'нет данных')}",
    ]
    if item["control"]:
        lines.append(f"🌍 Из-за рубежа: {esc(item['control'])}")
    if item["bad_points"]:
        lines.append(f"🚫 Не отвечает из: {esc(', '.join(item['bad_points']))}")
    if item["incident"]:
        inc = item["incident"]
        lines.append(
            f"\n⏳ Проблема с {esc(mon.fmt_stamp(inc['started_at']))} — "
            f"{esc(mon.human_duration(time.time() - inc['started_at']))}"
        )
    lines.append(f"\n🕒 Последняя проверка: {esc(_age(item['last_check']))}")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data=f"monitor:t:{target_sid}")],
        [InlineKeyboardButton("⬅️ К списку", callback_data="monitor:board")],
    ])
    await safe_edit_query(query, "\n".join(lines), kb)


@admin_only
async def monitor_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    day = mon.state().get("day") or {}
    closed = day.get("incidents") or []
    snap = mon.status_snapshot()
    open_items = [i for i in snap["items"] if i["incident"]]

    lines = ["📉 <b>События за сутки</b>", "━━━━━━━━━━━━━━━"]
    if not closed and not open_items:
        lines.append("Пусто: за сегодня ни один адрес не терялся.")
    else:
        if open_items:
            lines.append("<b>Открытые:</b>")
            for item in open_items:
                inc = item["incident"]
                lines.append(
                    f"{mon.VERDICT_ICON.get(inc['kind'], '⚠️')} {esc(item['label'])} — "
                    f"{esc(mon.VERDICT_NAME.get(inc['kind'], inc['kind']))}, с "
                    f"{esc(mon.fmt_clock(inc['started_at']))}, уже "
                    f"{esc(mon.human_duration(time.time() - inc['started_at']))}"
                )
            lines.append("")
        if closed:
            lines.append("<b>Закрытые:</b>")
            for item in sorted(closed, key=lambda x: x["started_at"], reverse=True):
                lines.append(
                    f"✅ {esc(mon.fmt_clock(item['started_at']))}–"
                    f"{esc(mon.fmt_clock(item['ended_at']))} "
                    f"({esc(mon.human_duration(item['duration']))}) — {esc(item['title'])} — "
                    f"{esc(mon.VERDICT_NAME.get(item['kind'], item['kind']))}"
                )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Обновить", callback_data="monitor:events")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=BACK)],
    ])
    await safe_edit_query(query, "\n".join(lines), kb)


@admin_only
async def monitor_check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Запускаю проверку")
    await safe_edit_query(
        query,
        "🔄 <b>Проверяю все адреса</b>\n━━━━━━━━━━━━━━━\n"
        "Обход занимает от нескольких секунд до пары минут — зависит от числа серверов.\n"
        "Экран обновится сам.",
        None,
    )

    result = await mon.run_cycle(context.bot, notify=True)
    if result.get("skipped"):
        await safe_edit_query(
            query,
            "⏳ Проверка уже идёт по расписанию — дождитесь её окончания и обновите экран.",
            home_kb(),
        )
        return

    summary = result.get("summary") or {}
    lines = [
        "✅ <b>Проверка завершена</b>",
        "━━━━━━━━━━━━━━━",
        f"Адресов проверено: <b>{result.get('targets', 0)}</b> за {result.get('duration', 0)} с",
        "",
        f"🟢 норма: {summary.get(mon.OK, 0)}",
        f"🟠 частично: {summary.get(mon.DEGRADED, 0)}",
        f"🛑 блокировка в РФ: {summary.get(mon.RU_BLOCKED, 0)}",
        f"🔴 не отвечает: {summary.get(mon.DOWN, 0)}",
    ]
    if summary.get(mon.UNKNOWN):
        lines.append(f"⚪️ не измерили: {summary[mon.UNKNOWN]}")
    for issue in result.get("issues") or []:
        lines.append(f"\n⚠️ {esc(issue)}")

    await safe_edit_query(query, "\n".join(lines), home_kb())


@admin_only
async def monitor_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=BACK)]])
    await safe_edit_query(query, mon.build_daily_report(), kb)


@admin_only
async def monitor_mute_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1 час", callback_data="monitor:mute:60"),
            InlineKeyboardButton("4 часа", callback_data="monitor:mute:240"),
        ],
        [
            InlineKeyboardButton("8 часов", callback_data="monitor:mute:480"),
            InlineKeyboardButton("Сутки", callback_data="monitor:mute:1440"),
        ],
        [InlineKeyboardButton("⬅️ Назад", callback_data=BACK)],
    ])
    await safe_edit_query(
        query,
        "🔇 <b>Приглушить уведомления</b>\n━━━━━━━━━━━━━━━\n"
        "Проверки продолжатся и события запишутся в сводку — просто не будет "
        "сообщений в этот период. Удобно на время работ на серверах.\n\n"
        "На сколько замолчать?",
        kb,
    )


@admin_only
async def monitor_mute_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    minutes = int(query.data.split(":")[-1])
    mon.mute_for(minutes)
    await query.answer(f"Тихий режим на {minutes // 60} ч")
    await safe_edit_query(query, home_text(), home_kb())


@admin_only
async def monitor_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    mon.mute_for(0)
    await query.answer("Уведомления включены")
    await safe_edit_query(query, home_text(), home_kb())


@admin_only
async def monitor_selftest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка связки бот → пингер: живость, ключ, доступные страны."""
    query = update.callback_query
    await query.answer("Проверяю пингер")

    alive, reason = await geopinger.health()
    countries, err = await geopinger.points_countries()

    lines = [
        "🩺 <b>Проверка пингера</b>",
        "━━━━━━━━━━━━━━━",
        f"🌐 Адрес: <code>{esc(GEOPINGER_URL or 'не задан')}</code>",
        f"{'🟢' if alive else '🔴'} Сервис: {esc(reason)}",
    ]
    if countries:
        lines.append(f"🗺 Точки есть в странах: {esc(', '.join(sorted(countries)).upper())}")
        if "ru" not in [c.lower() for c in countries]:
            lines.append("⚠️ Точек в РФ нет — главная проверка работать не будет.")
    elif err:
        lines.append(f"⚠️ Список точек не получен: {esc(err)}")

    probe = await geopinger.ping("ya.ru", countries=["ru"], limit=3)
    if probe.usable:
        lines.append(f"\n✅ Тестовый пинг ya.ru из РФ: {esc(probe.short())}")
    else:
        lines.append(f"\n❌ Тестовый пинг не прошёл: {esc(probe.error or 'нет данных')}")
        lines.append("Проверьте ключ доступа и что порт пингера открыт для бота.")

    lines.append(
        f"\nИнцидент открывается после {MONITOR_FAIL_STREAK} подряд неудачных обходов "
        f"(то есть примерно через {MONITOR_FAIL_STREAK * MONITOR_INTERVAL_SEC // 60} мин)."
    )

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=BACK)]])
    await safe_edit_query(query, "\n".join(lines), kb)


# ── Фоновые задачи ──────────────────────────────────────────────────────────

async def monitor_cycle_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Регулярный обход всех адресов."""
    try:
        await mon.run_cycle(context.bot, notify=True)
    except Exception:  # noqa: BLE001 — задача не должна умирать насовсем
        import logging
        logging.getLogger(__name__).exception("Цикл мониторинга сорвался")


async def monitor_report_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Раз в минуту смотрим, не пора ли отправить суточную сводку."""
    try:
        if not mon.report_due():
            return
        from bot.utils.notify import broadcast_admins
        await broadcast_admins(context.bot, mon.build_daily_report())
        mon.mark_report_sent()
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception("Не удалось отправить суточную сводку")
