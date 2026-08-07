import { useEffect, useState, useCallback, useRef, type ReactNode } from 'react';
import { analyticsApi, monitorApi, invoicesApi } from '../api/client';
import { Icon } from '../components/Icon';

interface PlatformBucket {
  total: number; premium: number; free: number;
  new24h: number; active24h: number;
  onlineNow: number; onlinePremium: number; onlineFree: number;
}

interface UserSummary {
  total: number; premium: number; free: number;
  new24h: number; active24h: number;
  onlineNow: number; onlinePremium: number; onlineFree: number;
  byPlatform?: {
    android?: PlatformBucket;
    ios?: PlatformBucket;
    unknown?: PlatformBucket;
  };
}
interface ServerStat {
  ipAddress: string; country: string; countryCode: string;
  status: boolean; premium: boolean; onlineUsers: number;
}
interface VlessStat {
  ipAddress: string; domain: string; description: string; onlineUsers: number;
}
interface ServersStats {
  totalServers: number; ikev2Servers: number; vlessServers: number; awgServers: number;
  totalOnline: number; ikev2Online: number; vlessOnline: number; awgOnline: number;
  servers: ServerStat[]; vlessServersList: VlessStat[]; awgServersList: ServerStat[];
}

interface MonitorStatus {
  isUp: boolean; latency: number; statusText: string;
  downtime: string; moscowTime: string;
}

interface PaymentStats {
  todayCount: number; todaySum: number;
  weekCount: number; weekSum: number;
  monthCount: number; monthSum: number;
  totalPaid: number; totalSum: number;
  /** Оплаты за всё время, по дням */
  dailyPayments: { date: string; count: number; sum: number }[];
  dailyPaymentsCount: { date: string; count: number }[];
  chartFrom: string;
  chartTo: string;
}

const fmt = (value: number | undefined | null) => (value ?? 0).toLocaleString('ru-RU');

export function Dashboard() {
  const [summary, setSummary] = useState<UserSummary | null>(null);
  const [servers, setServers] = useState<ServersStats | null>(null);
  const [monitor, setMonitor] = useState<MonitorStatus | null>(null);
  const [payments, setPayments] = useState<PaymentStats | null>(null);
  const [mainLoading, setMainLoading] = useState(true);
  const [paymentsLoading, setPaymentsLoading] = useState(true);

  const loadMain = useCallback(async () => {
    try {
      const [s, srv, mon] = await Promise.all([
        analyticsApi.summary(),
        analyticsApi.serversStats(),
        monitorApi.status(),
      ]);
      if (s.success) setSummary(s.data);
      if (srv.success) setServers(srv.data);
      setMonitor(mon);
    } catch {} finally {
      setMainLoading(false);
    }
  }, []);

  const loadPayments = useCallback(async () => {
    setPaymentsLoading(true);
    try {
      let allPaid: { invoiceId: string; userId: string; amount: string; currency: string; status: string; plan: string; created: string }[] = [];
      const PAGE = 200;
      const first = await invoicesApi.all(0, PAGE);
      if (first.success && first.data) {
        allPaid = first.data.filter((i: { status: string }) => i.status === 'PAID' || i.status === 'InvoiceStatus.PAID');
        const total = first.total || 0;
        if (total > PAGE) {
          const pages = Math.ceil(total / PAGE);
          const rest = await Promise.all(
            Array.from({ length: pages - 1 }, (_, idx) => invoicesApi.all((idx + 1) * PAGE, PAGE))
          );
          for (const r of rest) {
            if (r.success && r.data) {
              allPaid = allPaid.concat(r.data.filter((i: { status: string }) => i.status === 'PAID' || i.status === 'InvoiceStatus.PAID'));
            }
          }
        }
      }

      const now = Date.now();
      const day = 86400000;
      const calc = (since: number) => {
        const filtered = allPaid.filter((i) => {
          const ts = i.created ? new Date(i.created).getTime() : 0;
          return ts >= since;
        });
        return {
          count: filtered.length,
          sum: filtered.reduce((a, i) => a + (parseFloat(i.amount) || 0), 0),
        };
      };
      const t = calc(now - day);
      const w = calc(now - 7 * day);
      const m = calc(now - 30 * day);
      const totalSum = allPaid.reduce((a, i) => a + (parseFloat(i.amount) || 0), 0);

      // ── История за всё время, строго по дням ─────────────────
      const paidTs = allPaid
        .map((i) => ({ ts: i.created ? new Date(i.created).getTime() : 0, amount: parseFloat(i.amount) || 0 }))
        .filter((x) => x.ts > 0)
        .sort((a, b) => a.ts - b.ts);

      const startOfDay = (ts: number) => {
        const d = new Date(ts);
        d.setHours(0, 0, 0, 0);
        return d.getTime();
      };

      const minTs = paidTs.length ? paidTs[0].ts : now;
      const spanDays = Math.max(1, Math.ceil((now - minTs) / day));
      const withYear = spanDays > 365;

      const labelFor = (ts: number) => {
        const d = new Date(ts);
        return d.toLocaleDateString('ru-RU', {
          day: '2-digit',
          month: '2-digit',
          ...(withYear ? { year: '2-digit' as const } : {}),
        });
      };

      const buckets = new Map<number, { count: number; sum: number }>();
      let cursor = startOfDay(minTs);
      const endDay = startOfDay(now);
      let guard = 0;
      while (cursor <= endDay && guard < 10000) {
        buckets.set(cursor, { count: 0, sum: 0 });
        const d = new Date(cursor);
        d.setDate(d.getDate() + 1);
        cursor = d.getTime();
        guard += 1;
      }

      for (const p of paidTs) {
        const b = startOfDay(p.ts);
        const cur = buckets.get(b) || { count: 0, sum: 0 };
        cur.count += 1;
        cur.sum += p.amount;
        buckets.set(b, cur);
      }

      const dailyPayments = Array.from(buckets.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([ts, v]) => ({
          date: labelFor(ts),
          count: v.count,
          sum: Math.round(v.sum * 100) / 100,
        }));

      setPayments({
        todayCount: t.count, todaySum: t.sum,
        weekCount: w.count, weekSum: w.sum,
        monthCount: m.count, monthSum: m.sum,
        totalPaid: allPaid.length, totalSum,
        dailyPayments,
        dailyPaymentsCount: dailyPayments.map((d) => ({ date: d.date, count: d.count })),
        chartFrom: new Date(minTs).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }),
        chartTo: new Date(now).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }),
      });
    } finally {
      setPaymentsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMain();
    loadPayments();
    const t = setInterval(loadMain, 15000);
    return () => clearInterval(t);
  }, [loadMain, loadPayments]);

  return (
    <div className="dashboard-page dashboard-compact flex-col gap-6">
      <div className="page-header">
        <div>
          <div className="page-title">Статистика</div>
          <div className="page-subtitle">{new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })} · обновление каждые 15 секунд</div>
        </div>
      </div>

      <div className="dashboard-status-row">
        <div className={`dashboard-api-pill ${monitor === null ? 'pending' : monitor.isUp ? 'up' : 'down'}`}>
          <span className="pulse-dot" />
          <span>{monitor === null ? 'Подключаемся к API…' : `API ${monitor.isUp ? 'онлайн' : 'офлайн'}`}</span>
        </div>
        <span>Задержка: <b>{monitor?.latency ?? '—'} мс</b></span>
        <span>Статус: <b>{monitor?.statusText || '—'}</b></span>
        <span>Обновлено: <b>{monitor?.moscowTime || '—'}</b></span>
        {monitor?.downtime && monitor.downtime !== '—' && <span className="badge badge-danger">Простой: {monitor.downtime}</span>}
      </div>

      <section className="dashboard-kpi-grid compact">
        <StatCard label="Пользователи" value={summary?.total ?? 0} icon="users" sub={`Бесплатных ${fmt(summary?.free)} Премиум ${fmt(summary?.premium)}`} loading={mainLoading} />
        <StatCard
          label="Активность за 5м"
          value={summary?.onlineNow ?? 0}
          icon="wifi"
          variant="success"
          valueAside={
            !mainLoading ? (
              <span
                className="stat-value-aside"
                title={`Премиум ${fmt(summary?.onlinePremium)} · Бесплатный ${fmt(summary?.onlineFree)}`}
              >
                Прем. {fmt(summary?.onlinePremium)} · Беспл. {fmt(summary?.onlineFree)}
              </span>
            ) : null
          }
          sub="Сколько юзеров за последние 5 мин сходили в API"
          loading={mainLoading}
        />
        <StatCard label="Активные за 24ч" value={summary?.active24h ?? 0} icon="activity" sub="Сколько активных пользователей было за последние сутки" loading={mainLoading} />
        <StatCard label="Новые за 24ч" value={summary?.new24h ?? 0} icon="plus" variant="info" sub="Сколько пользователей зарегистрировалось за последние сутки" loading={mainLoading} />
        <StatCard label="Серверы" value={servers?.totalServers ?? 0} icon="serverIkev2" sub={`IKEv2 ${fmt(servers?.ikev2Servers)} · VLESS ${fmt(servers?.vlessServers)} · AWG ${fmt(servers?.awgServers)}`} loading={mainLoading} />
        <StatCard label="Подключений" value={servers?.totalOnline ?? 0} icon="globe" variant="success" sub={`IKEv2 ${fmt(servers?.ikev2Online)} · VLESS ${fmt(servers?.vlessOnline)} · AWG ${fmt(servers?.awgOnline)}`} loading={mainLoading} />
      </section>

      {/* Платформы + выручка в одной сетке — без пустой ячейки справа от «Неизвестно» */}
      <section className="dashboard-kpi-grid compact">
        <StatCard
          label="Android клиенты"
          value={summary?.byPlatform?.android?.total ?? 0}
          icon="users"
          sub={`Премиум ${fmt(summary?.byPlatform?.android?.premium)} · 24ч ${fmt(summary?.byPlatform?.android?.new24h)} · онлайн ${fmt(summary?.byPlatform?.android?.onlineNow)}`}
          loading={mainLoading}
        />
        <StatCard
          label="iOS клиенты"
          value={summary?.byPlatform?.ios?.total ?? 0}
          icon="users"
          variant="info"
          sub={`Премиум ${fmt(summary?.byPlatform?.ios?.premium)} · 24ч ${fmt(summary?.byPlatform?.ios?.new24h)} · онлайн ${fmt(summary?.byPlatform?.ios?.onlineNow)}`}
          loading={mainLoading}
        />
        <StatCard
          label="Неизвестно"
          value={summary?.byPlatform?.unknown?.total ?? 0}
          icon="users"
          variant="warn"
          sub={`Ещё не заходили, чтобы узнать их устройства · Премиум ${fmt(summary?.byPlatform?.unknown?.premium)}`}
          loading={mainLoading}
        />
        <StatCard label="Деньги за сегодня" value={payments?.todaySum ?? 0} icon="dollar" suffix="₽" sub={`${payments?.todayCount ?? 0} покупок`} loading={paymentsLoading} />
        <StatCard label="Деньги за 7 дней" value={payments?.weekSum ?? 0} icon="dollar" variant="info" suffix="₽" sub={`${payments?.weekCount ?? 0} покупок`} loading={paymentsLoading} />
        <StatCard label="Деньги за месяц" value={payments?.monthSum ?? 0} icon="dollar" variant="success" suffix="₽" sub={`${payments?.monthCount ?? 0} покупок`} loading={paymentsLoading} />
        <StatCard label="Всего денег" value={payments?.totalSum ?? 0} icon="dollar" variant="warn" suffix="₽" sub={`${payments?.totalPaid ?? 0} покупок`} loading={paymentsLoading} />
      </section>

      <section className="card dashboard-panel compact-panel">
        <div className="card-header compact-header">
          <div>
            <div className="card-title">Онлайн по серверам</div>
          </div>
          <span className="badge badge-accent">{fmt(servers?.totalOnline)} онлайн</span>
        </div>
        <div className="card-body">
          {servers ? (
            <div className="compact-server-sections">
              {servers.servers.length > 0 && (
                <ServerCardGroup title="IKEv2" icon="shield" items={servers.servers.map(s => ({
                  name: s.country || s.ipAddress || 'IKEv2',
                  ip: s.ipAddress || 'без IP',
                  countryCode: s.countryCode,
                  status: s.status,
                  premium: s.premium,
                  online: s.onlineUsers,
                }))} />
              )}
              {servers.vlessServersList.length > 0 && (
                <ServerCardGroup title="VLESS" icon="bolt" items={servers.vlessServersList.map(s => {
                  const desc = s.description || '';
                  const cc = desc.match(/^([A-Z]{2})/i)?.[1] || '';
                  return {
                    name: desc || 'VLESS',
                    ip: s.domain || s.ipAddress || 'без адреса',
                    countryCode: cc,
                    status: true,
                    premium: false,
                    online: s.onlineUsers,
                  };
                })} />
              )}
              {servers.awgServersList.length > 0 && (
                <ServerCardGroup title="AWG" icon="globe" items={servers.awgServersList.map(s => ({
                  name: s.country || s.ipAddress || 'AWG',
                  ip: s.ipAddress || 'без IP',
                  countryCode: s.countryCode,
                  status: s.status,
                  premium: s.premium,
                  online: s.onlineUsers,
                }))} />
              )}
              {servers.totalServers === 0 && <div className="empty-state"><span>Серверов пока нет</span></div>}
            </div>
          ) : (
            mainLoading
              ? <div className="loading-center"><span className="spinner" /><span style={{ marginLeft: 8 }}>Загрузка серверов…</span></div>
              : <div className="empty-state"><span>Нет данных по серверам</span></div>
          )}
        </div>
      </section>

      <section className="card dashboard-panel payments-chart-panel">
        <div className="card-header compact-header">
          <div>
            <div className="card-title">Оплата за всё время</div>
            <div className="dashboard-card-subtitle">
              {payments
                ? `${payments.chartFrom} — ${payments.chartTo} · по дням · ${fmt(payments.totalPaid)} покупок · ${fmt(Math.round(payments.totalSum))} ₽`
                : 'Загрузка истории…'}
            </div>
          </div>
        </div>
        <div className="card-body payments-chart-body">
          {payments?.dailyPayments ? (
            payments.dailyPayments.length === 0 ? (
              <div className="empty-state"><span>Оплат пока нет</span></div>
            ) : (
              <LineChart
                height={320}
                series={[
                  { data: payments.dailyPayments.map((d, i) => ({ ts: i, value: d.sum })), color: 'var(--success)', label: 'Сумма ₽' },
                ]}
                labels={payments.dailyPayments.map((d) => d.date)}
                pointCounts={payments.dailyPayments.map((d) => d.count)}
                totalCount={payments.totalPaid}
              />
            )
          ) : (
            <div className="loading-center"><span className="spinner" /></div>
          )}
        </div>
      </section>
    </div>
  );
}

function StatCard({ label, value, variant, icon, sub, progress, suffix, loading, displayValue, valueAside }: {
  label: string; value: number; variant?: string; icon?: string; sub?: string; progress?: number; suffix?: string; loading?: boolean; displayValue?: string; valueAside?: ReactNode;
}) {
  return (
    <div className={`stat-card dashboard-stat-card compact ${variant || ''}`}>
      <div className="flex items-center justify-between">
        <span className="stat-label">{label}</span>
        {icon && <Icon name={icon} size={16} className="text-muted" />}
      </div>
      {loading
        ? <div className="stat-value"><span className="spinner" style={{ width: 20, height: 20 }} /></div>
        : (
          <div className="stat-value-row">
            <div className="stat-value">
              {displayValue || fmt(value)}
              {suffix && <span style={{ fontSize: 16, fontWeight: 600, marginLeft: 4 }}>{suffix}</span>}
            </div>
            {valueAside}
          </div>
        )
      }
      {sub && <div className="stat-sub" title={sub}>{loading ? 'загрузка…' : sub}</div>}
      {progress != null && <div className="stat-progress"><span style={{ width: `${Math.min(100, Math.max(0, progress))}%` }} /></div>}
    </div>
  );
}

function ServerCardGroup({ title, icon, items }: {
  title: string;
  icon: string;
  items: { name: string; ip: string; countryCode?: string; status: boolean; premium: boolean; online: number }[];
}) {
  const totalOnline = items.reduce((sum, s) => sum + s.online, 0);

  return (
    <div className="compact-server-section">
      <div className="compact-section-title">
        <span><Icon name={icon} size={16} /> {title}</span>
        <b>{fmt(totalOnline)} онлайн</b>
      </div>
      <div className="dashboard-kpi-grid compact">
        {items.map((s, i) => {
          const cc = (s.countryCode || '').toUpperCase();
          return (
            <div key={`${title}-${s.ip}-${i}`} className="stat-card dashboard-stat-card compact">
              <div className="flex items-center justify-between">
                <span className="stat-label" style={{ maxWidth: '75%' }}>
                  {cc.length === 2 && (
                    <img
                      src={`https://flagcdn.com/24x18/${cc.toLowerCase()}.png`}
                      alt={cc}
                      style={{ width: 20, height: 14, marginRight: 6, borderRadius: 2, verticalAlign: 'middle' }}
                      onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                    />
                  )}
                  <span className="truncate">{s.name}</span>
                </span>
                <div className="flex items-center gap-1">
                  {s.premium && <Icon name="star" size={12} style={{ color: 'var(--warn)' }} />}
                  <span className={`badge ${s.status ? 'badge-success' : 'badge-danger'}`}>{s.status ? 'Вкл' : 'Выкл'}</span>
                </div>
              </div>
              <div className="stat-value">{fmt(s.online)}</div>
              <div className="stat-sub mono truncate" title={s.ip}>{s.ip}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Линейный график (сумма ₽).
 * pointCounts — кол-во покупок по дням: только в тултипе и внизу справа, без второй линии.
 */
function LineChart({ series, labels, height = 220, pointCounts, totalCount }: {
  series: { data: { ts: number; value: number }[]; color: string; label: string }[];
  labels?: string[];
  height?: number;
  /** Кол-во покупок по тем же индексам, что series[0] */
  pointCounts?: number[];
  totalCount?: number;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<{ idx: number; x: number } | null>(null);

  const W = 800;
  const H = height;
  const PAD = { t: 20, r: 12, b: 36, l: 52 };
  const cw = W - PAD.l - PAD.r;
  const ch = H - PAD.t - PAD.b;

  const maxes = series.map((s) => Math.max(...s.data.map((d) => d.value), 1));
  const maxIdx = Math.max(...series.map((s) => s.data.length), 1) - 1;
  const n = maxIdx + 1;

  const toX = (i: number) => PAD.l + (i / Math.max(maxIdx, 1)) * cw;
  const toY = (v: number, maxVal: number) => PAD.t + ch - (v / maxVal) * ch;

  const buildPath = (data: { ts: number; value: number }[], maxVal: number) => {
    if (data.length < 2) return { line: '', area: '' };
    const pts = data.map((d, i) => ({ x: toX(i), y: toY(d.value, maxVal) }));
    let line = `M${pts[0].x},${pts[0].y}`;
    for (let i = 1; i < pts.length; i++) {
      const prev = pts[i - 1];
      const curr = pts[i];
      const cpx1 = prev.x + (curr.x - prev.x) * 0.4;
      const cpx2 = curr.x - (curr.x - prev.x) * 0.4;
      line += ` C${cpx1},${prev.y} ${cpx2},${curr.y} ${curr.x},${curr.y}`;
    }
    const area = line + ` L${pts[pts.length - 1].x},${PAD.t + ch} L${pts[0].x},${PAD.t + ch} Z`;
    return { line, area };
  };

  const ticks = 5;
  const leftMax = maxes[0] || 1;
  const leftTicks = Array.from({ length: ticks + 1 }, (_, i) => Math.round((leftMax / ticks) * i));

  const labelStep = Math.max(1, Math.ceil(n / 10));
  const xLabels: string[] = (labels || []).map((l, i) =>
    (i === 0 || i === n - 1 || i % labelStep === 0) ? l : '',
  );

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const ctm = svg.getScreenCTM();
    if (!ctm) return;
    const svgX = (e.clientX - ctm.e) / ctm.a;
    const idx = Math.round(((svgX - PAD.l) / cw) * maxIdx);
    const clamped = Math.max(0, Math.min(maxIdx, idx));
    setHover({ idx: clamped, x: toX(clamped) });
  };

  const hoverLabel = hover ? (labels?.[hover.idx] || '') : '';
  const hoverCount = hover != null && pointCounts ? (pointCounts[hover.idx] ?? 0) : null;

  return (
    <div className="payments-line-chart">
      <div style={{ position: 'relative' }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          style={{ width: '100%', height }}
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHover(null)}
        >
          {leftTicks.map((v) => (
            <g key={`L${v}`}>
              <line
                x1={PAD.l}
                y1={toY(v, leftMax)}
                x2={W - PAD.r}
                y2={toY(v, leftMax)}
                stroke="var(--glass-border)"
                strokeWidth={1}
              />
              <text
                x={PAD.l - 6}
                y={toY(v, leftMax) + 4}
                textAnchor="end"
                fill={series[0]?.color || 'var(--fg-muted)'}
                fontSize={10}
                opacity={0.9}
              >
                {v}
              </text>
            </g>
          ))}

          {xLabels.map((l, i) => l ? (
            <text key={i} x={toX(i)} y={H - 6} textAnchor="middle" fill="var(--fg-muted)" fontSize={9}>{l}</text>
          ) : null)}

          {series.map((s, si) => {
            const maxVal = maxes[si] || 1;
            const { line, area } = buildPath(s.data, maxVal);
            return (
              <g key={si}>
                <path d={area} fill={s.color} opacity={0.12} />
                <path
                  d={line}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={2.2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </g>
            );
          })}

          {hover && (
            <g>
              <line
                x1={hover.x}
                y1={PAD.t}
                x2={hover.x}
                y2={PAD.t + ch}
                stroke="var(--fg-muted)"
                strokeWidth={1}
                strokeDasharray="4 3"
              />
              {series.map((s, si) => {
                const val = s.data[hover.idx]?.value ?? 0;
                const cy = toY(val, maxes[si] || 1);
                return (
                  <g key={si}>
                    <circle cx={hover.x} cy={cy} r={4.5} fill={s.color} stroke="var(--panel-surface)" strokeWidth={2} />
                  </g>
                );
              })}
            </g>
          )}

          {series[0] && (
            <g>
              <rect x={PAD.l} y={2} width={12} height={12} rx={2} fill={series[0].color} />
              <text x={PAD.l + 16} y={12} fill="var(--fg-secondary)" fontSize={10}>
                {series[0].label}
              </text>
            </g>
          )}
        </svg>

        {hover && (
          <div style={{
            position: 'absolute', top: 8, right: 12,
            background: 'var(--panel-surface-strong)', border: '1px solid var(--glass-border)',
            borderRadius: 8, padding: '8px 12px', fontSize: 12, lineHeight: 1.6,
            pointerEvents: 'none', zIndex: 10, minWidth: 150,
          }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{hoverLabel}</div>
            {series.map((s, si) => (
              <div key={si} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: s.color, flexShrink: 0 }} />
                <span>{s.label}: <b>{fmt(s.data[hover.idx]?.value ?? 0)}</b></span>
              </div>
            ))}
            {hoverCount != null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: '#8b5cf6', flexShrink: 0 }} />
                <span>Покупок: <b>{fmt(hoverCount)}</b></span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Внизу только итог; день/кол-во — в тултипе при hover */}
      {totalCount != null && (
        <div className="payments-chart-meta">
          <span className="payments-chart-meta-left">
            Всего покупок: <b>{fmt(totalCount)}</b>
          </span>
        </div>
      )}
    </div>
  );
}
