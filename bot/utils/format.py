"""Утилиты форматирования для бота.

Все тексты бота рендерим в HTML (parse_mode="HTML") — это надёжнее
легаси-Markdown: спецсимволы в данных (домены, описания, пароли)
не ломают отображение, достаточно прогнать значение через esc().
"""
import hashlib
import html


def esc(value) -> str:
    """Экранирует значение для безопасной вставки в HTML-текст."""
    return html.escape(str(value if value is not None else ""))


def code(value) -> str:
    """Моноширинное значение (копируется по тапу в Telegram)."""
    return f"<code>{esc(value)}</code>"


def field(value, placeholder: str = "—") -> str:
    """Человеческое отображение значения: '0' и пусто показываем как «—»."""
    v = str(value if value is not None else "").strip()
    if v in ("", "0"):
        return placeholder
    return v


def sid(value: str) -> str:
    """Короткий стабильный ID для callback_data.

    Telegram ограничивает callback_data 64 байтами, а идентификаторы серверов
    (домены/IP) бывают длинными и содержат любые символы. Поэтому в кнопки
    кладём только 12-символьный hash, а полное значение восстанавливаем,
    перечитав список с API и сматчив hash.
    """
    return hashlib.sha1(str(value).encode()).hexdigest()[:12]


def resolve_sid(target_sid: str, values: list[str]) -> str | None:
    """Находит исходное значение по его sid()."""
    for v in values:
        if sid(v) == target_sid:
            return v
    return None
