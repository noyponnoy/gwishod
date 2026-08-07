import { useState, useCallback, useEffect } from 'react';
import { invoicesApi, tariffsApi } from '../api/client';
import { Icon } from '../components/Icon';
import { fmtDate, val } from '../utils/format';

interface Invoice {
  invoiceId: string; userId: string; amount: string; currency: string;
  status: string; plan: string; payUrl: string; created: string; updated: string;
  FKoperationId: string; P_EMAIL: string; P_PHONE: string;
  payerAccount: string; commission: string;
}

const PAGE_SIZE = 25;

export function Invoices() {
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'PAID' | 'PENDING' | 'FAILED'>('all');
  const [tariffMap, setTariffMap] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, t] = await Promise.all([
        invoicesApi.all(skip, PAGE_SIZE),
        tariffsApi.all(),
      ]);
      if (r.success) {
        setInvoices(r.data || []);
        setTotal(r.total || 0);
      }
      if (t.success && t.data) {
        const map: Record<string, string> = {};
        for (const tf of t.data) {
          map[tf.technicalName] = tf.name;
        }
        setTariffMap(map);
      }
    } finally {
      setLoading(false);
    }
  }, [skip]);

  useEffect(() => { load(); }, [load]);

  const isPendingStatus = (status: string) =>
    status === 'PENDING' || status === 'CREATED' ||
    status === 'InvoiceStatus.PENDING' || status === 'InvoiceStatus.CREATED';

  const filtered = filter === 'all'
    ? invoices
    : invoices.filter((i) => filter === 'PENDING' ? isPendingStatus(i.status) : i.status === filter);

  const currentPage = Math.floor(skip / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const statusBadge = (status: string) => {
    if (status === 'PAID' || status === 'InvoiceStatus.PAID') return <span className="badge badge-success">Оплачен</span>;
    if (isPendingStatus(status)) return <span className="badge badge-warn">Ожидание</span>;
    if (status === 'FAILED' || status === 'REJECTED') return <span className="badge badge-danger">Ошибка</span>;
    return <span className="badge badge-neutral">{status}</span>;
  };

  return (
    <div className="flex-col gap-6">
      <div className="page-header">
        <div>
          <div className="page-title">Платежи</div>
          <div className="page-subtitle">Всего: {total}</div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load}>
          <Icon name="refresh" size={16} /> Обновить
        </button>
      </div>

      {/* Фильтр */}
      <div className="tabs" style={{ width: 'fit-content' }}>
        {(['all', 'PAID', 'PENDING', 'FAILED'] as const).map((f) => (
          <button key={f} className={`tab ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
            {f === 'all' ? 'Все' : f === 'PAID' ? 'Оплачены' : f === 'PENDING' ? 'Ожидают' : 'Ошибки'}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-body card-body-flush">
          {loading ? (
            <div className="loading-center"><span className="spinner" /> Загрузка…</div>
          ) : filtered.length === 0 ? (
            <div className="empty-state">
              <Icon name="invoice" size={48} className="empty-state-icon" />
              <div className="empty-state-title">Платежей нет</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="table table-mobile">
                <thead>
                  <tr>
                    <th>ID платежа</th>
                    <th>Тариф</th>
                    <th>Сумма</th>
                    <th>Статус</th>
                    <th>Дата</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((inv, i) => (
                    <tr key={i}>
                      <td data-label="ID платежа" className="mono" style={{ wordBreak: 'break-all' }} title={inv.invoiceId}>{inv.invoiceId}</td>
                      <td data-label="Тариф">{tariffMap[inv.plan] || val(inv.plan)}</td>
                      <td data-label="Сумма" className="mono" style={{ fontWeight: 600 }}>{val(inv.amount)} ₽</td>
                      <td data-label="Статус">{statusBadge(inv.status)}</td>
                      <td data-label="Дата" className="text-muted">{fmtDate(inv.created)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {filtered.length > 0 && (
          <div className="pagination">
            <div className="pagination-info">
              {skip + 1}–{Math.min(skip + PAGE_SIZE, total)} из {total}
            </div>
            <div className="pagination-btns">
              <button className="page-btn" disabled={skip === 0} onClick={() => setSkip(0)}>«</button>
              <button className="page-btn" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}>
                <Icon name="chevronLeft" size={14} />
              </button>
              <span className="page-btn active">{currentPage} / {totalPages}</span>
              <button className="page-btn" disabled={skip + PAGE_SIZE >= total} onClick={() => setSkip(skip + PAGE_SIZE)}>
                <Icon name="chevronRight" size={14} />
              </button>
              <button className="page-btn" disabled={skip + PAGE_SIZE >= total} onClick={() => setSkip((totalPages - 1) * PAGE_SIZE)}>»</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
