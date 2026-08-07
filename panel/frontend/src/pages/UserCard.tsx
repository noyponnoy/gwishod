import { useState, useCallback, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { usersApi } from '../api/client';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { useToast } from '../context/ToastContext';
import { fmtBytes, fmtDate, fmtRelative, isPremiumActive, platformBadge, val, copyToClipboard } from '../utils/format';

interface UserDetail {
  id: string; email: string; isAnonymous: boolean; isPremium: boolean;
  premiumEnd: string; createdAt: string; lastLogin: string;
  totalUpload: number; totalDownload: number; countryCode: string;
  deviceId: string; sourceIp: string;
  platform?: string; bundleId?: string; firstPlatform?: string;
  platformUpdatedAt?: string;
  invoices: InvoiceItem[];
}
interface InvoiceItem {
  invoiceId: string; amount: string; status: string; plan: string; created: string;
}

const PREMIUM_OPTIONS = [1, 3, 7, 30, 90, 180];

export function UserCard() {
  const { deviceId } = useParams<{ deviceId: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  const [user, setUser] = useState<UserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [premiumModal, setPremiumModal] = useState(false);
  const [selectedDays, setSelectedDays] = useState(30);
  const [actionLoading, setActionLoading] = useState(false);
  const [revokeConfirm, setRevokeConfirm] = useState(false);

  const load = useCallback(async () => {
    if (!deviceId) return;
    setLoading(true);
    try {
      const r = await usersApi.get(deviceId);
      if (r.success) setUser(r.data);
      else { toast.error('Не найден', r.message); }
    } finally {
      setLoading(false);
    }
  }, [deviceId, toast]);

  useEffect(() => { load(); }, [load]);

  const handleSetPremium = async () => {
    if (!user?.deviceId) return;
    setActionLoading(true);
    try {
      const r = await usersApi.setPremium(user.deviceId, selectedDays);
      if (r.success) {
        toast.success('Премиум выдан', `${selectedDays} дн. до ${fmtDate(r.premiumEnd)}`);
        setPremiumModal(false);
        load();
      } else {
        toast.error('Ошибка', r.message);
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleRevoke = async () => {
    if (!user?.deviceId) return;
    setActionLoading(true);
    try {
      const r = await usersApi.revokePremium(user.deviceId);
      if (r.success) {
        toast.success('Премиум отозван');
        setRevokeConfirm(false);
        load();
      } else {
        toast.error('Ошибка', r.message);
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleCopy = async (text: string, label: string) => {
    if (await copyToClipboard(text)) toast.info('Скопировано', label);
  };

  if (loading) {
    return <div className="loading-center"><span className="spinner spinner-lg" /> Загрузка пользователя…</div>;
  }

  if (!user) {
    return (
      <div className="empty-state">
        <Icon name="users" size={48} className="empty-state-icon" />
        <div className="empty-state-title">Пользователь не найден</div>
        <Link to="/users" className="btn btn-secondary mt-4">← К списку</Link>
      </div>
    );
  }

  const premiumActive = isPremiumActive(user.premiumEnd, user.isPremium);
  const totalTraffic = fmtBytes(Number(user.totalUpload) + Number(user.totalDownload));

  return (
    <div className="flex-col gap-6">
      {/* Хедер */}
      <div className="page-header">
        <div className="flex items-center gap-3">
          <button className="btn btn-ghost btn-icon" onClick={() => navigate(-1)}>
            <Icon name="chevronLeft" size={22} />
          </button>
          <div>
            <div className="page-title flex items-center gap-2">
              <span className="avatar">{(user.email || '?')[0].toUpperCase()}</span>
              Карточка пользователя
              <span className="badge badge-neutral">{platformBadge(user.platform)}</span>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          {premiumActive ? (
            <button className="btn btn-danger" onClick={() => setRevokeConfirm(true)}>
              <Icon name="close" size={18} /> Забрать Премиум
            </button>
          ) : null}
          <button className="btn btn-primary" onClick={() => setPremiumModal(true)}>
            <Icon name="star" size={18} /> {premiumActive ? 'Продлить Премиум' : 'Выдать Премиум'}
          </button>
        </div>
      </div>

      {/* Статус и трафик */}
      <div className="stat-grid">
        <div className={`stat-card ${premiumActive ? 'warn' : 'neutral'}`}>
          <div className="flex items-center justify-between">
            <span className="stat-label">Премиум</span>
            <Icon name="star" size={16} className="text-muted" />
          </div>
          <div className="stat-value">{premiumActive ? 'Активен' : 'Нет'}</div>
          {premiumActive && <div className="stat-sub">До {fmtDate(user.premiumEnd)}</div>}
        </div>
        <div className="stat-card info">
          <span className="stat-label">Всего трафика</span>
          <div className="stat-value" style={{ fontSize: 22 }}>{totalTraffic}</div>
          <div className="stat-sub">↑ {fmtBytes(user.totalUpload)} · ↓ {fmtBytes(user.totalDownload)}</div>
        </div>
        <div className="stat-card success">
          <span className="stat-label">Последний вход</span>
          <div className="stat-value" style={{ fontSize: 16 }}>{fmtRelative(user.lastLogin)}</div>
          <div className="stat-sub">{fmtDate(user.lastLogin)}</div>
        </div>
        <div className="stat-card">
          <span className="stat-label">Регистрация</span>
          <div className="stat-value" style={{ fontSize: 16 }}>{fmtDate(user.createdAt)}</div>
        </div>
      </div>

      {/* Детали */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Детали</div>
        </div>
        <div className="card-body">
          <div className="detail-grid">
            <DetailItem label="Device ID" value={user.deviceId || user.id} mono copy onCopy={() => handleCopy(user.deviceId || user.id, 'Device ID')} />
            <DetailItem label="User ID" value={user.id} mono copy onCopy={() => handleCopy(user.id, 'User ID')} />
            <DetailItem label="Платформа" value={platformBadge(user.platform)} />
            <DetailItem label="Bundle ID" value={val(user.bundleId, '—')} mono copy={!!user.bundleId} onCopy={() => handleCopy(user.bundleId || '', 'Bundle ID')} />
            <DetailItem label="Первая платформа" value={platformBadge(user.firstPlatform || user.platform)} />
            <DetailItem label="Email" value={val(user.email, '—')} copy={!!user.email} onCopy={() => handleCopy(user.email, 'Email')} />
            <DetailItem label="Тип" value={user.isAnonymous ? 'Анонимный' : 'Обычный'} />
            <DetailItem label="Страна" value={user.countryCode && user.countryCode !== '0' ? user.countryCode.toUpperCase() : '—'} />
            <DetailItem label="IP-адрес" value={val(user.sourceIp, '—')} mono copy={!!user.sourceIp} onCopy={() => handleCopy(user.sourceIp || '', 'IP')} />
            <DetailItem label="Премиум до" value={premiumActive ? fmtDate(user.premiumEnd) : '—'} />
            <DetailItem label="Загружено" value={fmtBytes(user.totalUpload)} mono />
            <DetailItem label="Скачано" value={fmtBytes(user.totalDownload)} mono />
          </div>
        </div>
      </div>

      {/* Платежи */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Платежи пользователя</div>
          <Link to="/invoices" className="btn btn-ghost btn-sm">Все платежи →</Link>
        </div>
        <div className="card-body card-body-flush">
          {user.invoices && user.invoices.length > 0 ? (
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
                  {user.invoices.map((inv, i) => (
                    <tr key={i}>
                      <td data-label="ID платежа" className="mono truncate" style={{ maxWidth: 140 }}>{inv.invoiceId}</td>
                      <td data-label="Тариф">{val(inv.plan)}</td>
                      <td data-label="Сумма" className="mono">{val(inv.amount)} ₽</td>
                      <td data-label="Статус">
                        <span className={`badge ${inv.status === 'PAID' ? 'badge-success' : inv.status === 'PENDING' ? 'badge-warn' : 'badge-neutral'}`}>
                          {inv.status}
                        </span>
                      </td>
                      <td data-label="Дата" className="text-muted">{fmtDate(inv.created)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">
              <Icon name="invoice" size={40} className="empty-state-icon" />
              <div className="empty-state-title">Платежей нет</div>
            </div>
          )}
        </div>
      </div>

      {/* Модалка выдачи Premium */}
      <Modal
        open={premiumModal}
        onClose={() => setPremiumModal(false)}
        title="Выдать Премиум"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setPremiumModal(false)}>Отмена</button>
            <button className="btn btn-primary" onClick={handleSetPremium} disabled={actionLoading}>
              {actionLoading && <span className="spinner" style={{ width: 16, height: 16 }} />}
              Выдать на {selectedDays} дн.
            </button>
          </>
        }
      >
        <p className="text-muted mb-4" style={{ fontSize: 14 }}>Выберите длительность Премиум подписки:</p>
        <div className="flex wrap gap-2">
          {PREMIUM_OPTIONS.map((d) => (
            <button
              key={d}
              className={`btn ${selectedDays === d ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setSelectedDays(d)}
            >
              {d} дн.
            </button>
          ))}
        </div>
        {premiumActive && (
          <div className="mt-4" style={{ background: 'var(--warn-bg)', color: 'var(--warn-fg)', padding: '12px 14px', borderRadius: 'var(--radius-md)', fontSize: 13 }}>
            ⚠ У пользователя уже есть активный Премиум. Выдача продлит подписку на {selectedDays} дней от текущего момента.
          </div>
        )}
      </Modal>

      {/* Подтверждение отзыва */}
      <ConfirmDialog
        open={revokeConfirm}
        title="Забрать Премиум?"
        message="Премиум подписка будет отменена немедленно. Пользователь потеряет доступ к Премиум серверам."
        confirmText="Забрать"
        danger
        loading={actionLoading}
        onConfirm={handleRevoke}
        onCancel={() => setRevokeConfirm(false)}
      />
    </div>
  );
}

function DetailItem({ label, value, mono, copy, onCopy }: {
  label: string; value: string; mono?: boolean; copy?: boolean; onCopy?: () => void;
}) {
  return (
    <div className="detail-item">
      <span className="detail-label">{label}</span>
      <div className="flex items-center gap-2">
        <span className={`detail-value ${mono ? 'mono' : ''}`} style={{ flex: 1, minWidth: 0 }} title={value}>
          <span className="truncate" style={{ display: 'inline-block', maxWidth: '100%' }}>{value}</span>
        </span>
        {copy && (
          <button className="btn btn-ghost btn-icon btn-sm" onClick={onCopy} title="Копировать">
            <Icon name="copy" size={14} />
          </button>
        )}
      </div>
    </div>
  );
}
