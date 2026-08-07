/**
 * Общие утилиты форматирования.
 */

/** Метка платформы клиента (android / ios / unknown). */
export function platformLabel(platform?: string | null): string {
  const p = (platform || 'unknown').toLowerCase();
  if (p === 'ios') return 'iOS';
  if (p === 'android') return 'Android';
  return 'Неизвестно';
}

/** Короткий бейдж-текст (без эмодзи). */
export function platformBadge(platform?: string | null): string {
  return platformLabel(platform);
}

/** Форматирует байты в читаемый вид (KB / MB / GB). */
export function fmtBytes(bytes: number | string | undefined | null): string {
  const b = Number(bytes) || 0;
  if (b < 1024) return `${b} B`;
  const kb = b / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  const gb = mb / 1024;
  if (gb < 1024) return `${gb.toFixed(2)} GB`;
  return `${(gb / 1024).toFixed(2)} TB`;
}

/** Парсит дату формата "Mon Jan 15 14:30:00 UTC 2025" и возвращает Date. */
export function parseApiDate(raw: string | undefined | null): Date | null {
  if (!raw) return null;
  // API отдаёт "Mon Jan 15 14:30:00 UTC 2025"
  // Заменяем "UTC" на "GMT" для совместимости с Date.parse в разных браузерах.
  const normalized = String(raw).replace(/\bUTC\b/, 'GMT');
  const d = new Date(normalized);
  if (isNaN(d.getTime())) {
    // Может быть timestamp-строка или число.
    const ts = Number(raw);
    if (!isNaN(ts)) return new Date(ts);
    return null;
  }
  return d;
}

/** Форматирует дату в "DD.MM.YYYY HH:MM". */
export function fmtDate(raw: string | undefined | null): string {
  const d = parseApiDate(raw);
  if (!d) return '—';
  return d.toLocaleString('ru-RU', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

/** Форматирует дату коротко: "DD.MM.YYYY". */
export function fmtDateShort(raw: string | undefined | null): string {
  const d = parseApiDate(raw);
  if (!d) return '—';
  return d.toLocaleDateString('ru-RU');
}

/** Относительное время: "5 мин назад", "2 ч назад". */
export function fmtRelative(raw: string | undefined | null): string {
  const d = parseApiDate(raw);
  if (!d) return '—';
  const diff = Date.now() - d.getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return 'только что';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} мин назад`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} ч назад`;
  const days = Math.floor(hr / 24);
  if (days < 30) return `${days} дн назад`;
  return fmtDateShort(raw);
}

/** Проверяет, активен ли premium (дата окончания в будущем). */
export function isPremiumActive(premiumEnd: string | undefined | null, isPremium?: boolean): boolean {
  if (isPremium === false) return false;
  const d = parseApiDate(premiumEnd);
  if (!d) return !!isPremium;
  return d.getTime() > Date.now();
}

/** Склонение существительных: 1 день, 2 дня, 5 дней. */
export function plural(n: number, forms: [string, string, string]): string {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return forms[0];
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return forms[1];
  return forms[2];
}

/** Безопасно возвращает строку или дефолт. */
export function val(v: any, def = '—'): string {
  if (v === null || v === undefined || v === '') return def;
  return String(v);
}

/** Копирует текст в буфер обмена. */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** Флаг-эмодзи по ISO country code. */
export function countryFlag(code: string | undefined | null): string {
  if (!code || code.length !== 2) return '🌐';
  const cc = code.toUpperCase();
  return String.fromCodePoint(...[...cc].map((c) => 127397 + c.charCodeAt(0)));
}
