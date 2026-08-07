import { useState, useCallback, useEffect } from 'react';
import { awgApi } from '../api/client';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { useToast } from '../context/ToastContext';
import { countryFlag, val } from '../utils/format';

interface AwgServer {
  country: string;
  ip_address: string;
  recommend: boolean;
  priority: number;
  config: string;
  created_at: number;
  premium: boolean;
  state: string;
  status: boolean;
  country_code: string;
}

interface EditForm {
  ip_address: string;
  country: string;
  state: string;
  country_code: string;
  premium: boolean;
  status: boolean;
}

export function ServersAwg() {
  const toast = useToast();
  const [servers, setServers] = useState<AwgServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [editTarget, setEditTarget] = useState<EditForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<AwgServer | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await awgApi.all();
      if (r.success) setServers(r.data || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggleField = async (s: AwgServer, field: 'status' | 'premium') => {
    const r = await awgApi.update({
      ip_address: s.ip_address,
      [field]: String(!s[field]),
    });
    if (r.success) {
      toast.success(field === 'status' ? (s.status ? 'Выключен' : 'Включён') : (s.premium ? 'Премиум снят' : 'Премиум включён'));
      load();
    } else {
      toast.error('Ошибка', r.message);
    }
  };

  const openEdit = (s: AwgServer) => {
    setEditTarget({
      ip_address: s.ip_address,
      country: s.country === '0' ? '' : s.country,
      state: s.state === '0' ? '' : s.state,
      country_code: s.country_code === '0' ? '' : s.country_code,
      premium: s.premium,
      status: s.status,
    });
  };

  const handleEdit = async () => {
    if (!editTarget) return;
    setSaving(true);
    try {
      const r = await awgApi.update({
        ip_address: editTarget.ip_address,
        country: editTarget.country,
        state: editTarget.state,
        country_code: editTarget.country_code,
        premium: String(editTarget.premium),
        status: String(editTarget.status),
      });
      if (r.success) {
        toast.success('Сервер обновлён');
        setEditTarget(null);
        load();
      } else {
        toast.error('Ошибка', r.message);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setSaving(true);
    try {
      const r = await awgApi.delete(deleteTarget.ip_address);
      if (r.success) {
        toast.success('Сервер удалён');
        setDeleteTarget(null);
        load();
      } else {
        toast.error('Ошибка', r.message);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-col gap-6">
      <div className="page-header">
        <div>
          <div className="page-title">Серверы AWG</div>
          <div className="page-subtitle">AmneziaWG · {servers.length} серверов</div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={load}>
          <Icon name="refresh" size={16} /> Обновить
        </button>
      </div>

      <div className="card">
        <div className="card-body card-body-flush">
          {loading ? (
            <div className="loading-center"><span className="spinner" /> Загрузка…</div>
          ) : servers.length === 0 ? (
            <div className="empty-state">
              <Icon name="serverAwg" size={48} className="empty-state-icon" />
              <div className="empty-state-title">Серверов нет</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="table table-mobile">
                <thead>
                  <tr>
                    <th>Страна</th>
                    <th>IP-адрес</th>
                    <th>Регион</th>
                    <th>Статус</th>
                    <th>Премиум</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {servers.map((s) => (
                    <tr key={s.ip_address}>
                      <td data-label="Страна">
                        <div className="flex items-center gap-2">
                          <span style={{ fontSize: 18 }}>{countryFlag(s.country_code)}</span>
                          <span style={{ fontWeight: 600 }}>{val(s.country, 'N/A')}</span>
                        </div>
                      </td>
                      <td data-label="IP-адрес" className="mono">{s.ip_address}</td>
                      <td data-label="Регион" className="text-muted">{val(s.state, '—')}</td>
                      <td data-label="Статус">
                        <div className="flex items-center gap-2">
                          <label className="switch" title={s.status ? 'Выключить' : 'Включить'}>
                            <input type="checkbox" checked={s.status} onChange={() => toggleField(s, 'status')} />
                            <span className="switch-slider" />
                          </label>
                          <span className={`badge ${s.status ? 'badge-success' : 'badge-danger'}`}>
                            {s.status ? 'Вкл' : 'Выкл'}
                          </span>
                        </div>
                      </td>
                      <td data-label="Премиум">
                        <label className="switch" title={s.premium ? 'Снять Премиум' : 'Включить Премиум'}>
                          <input type="checkbox" checked={s.premium} onChange={() => toggleField(s, 'premium')} />
                          <span className="switch-slider" />
                        </label>
                      </td>
                      <td data-label="" className="col-actions">
                        <div className="flex gap-1 justify-end">
                          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => openEdit(s)} title="Редактировать">
                            <Icon name="edit" size={16} />
                          </button>
                          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setDeleteTarget(s)} title="Удалить" style={{ color: 'var(--danger-fg)' }}>
                            <Icon name="trash" size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Edit modal */}
      <Modal
        open={!!editTarget}
        onClose={() => setEditTarget(null)}
        title="Редактирование AWG-сервера"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setEditTarget(null)}>Отмена</button>
            <button className="btn btn-primary" onClick={handleEdit} disabled={saving}>
              {saving && <span className="spinner" style={{ width: 16, height: 16 }} />}
              Сохранить
            </button>
          </>
        }
      >
        {editTarget && (
          <div className="flex-col gap-4">
            <div className="input-group">
              <label className="input-label">IP-адрес</label>
              <input className="input mono" value={editTarget.ip_address} disabled />
            </div>
            <div className="flex gap-4">
              <div className="input-group grow">
                <label className="input-label">Страна</label>
                <input className="input" value={editTarget.country} onChange={(e) => setEditTarget({ ...editTarget, country: e.target.value })} placeholder="Россия" />
              </div>
              <div className="input-group grow">
                <label className="input-label">Код страны</label>
                <input className="input mono" value={editTarget.country_code} onChange={(e) => setEditTarget({ ...editTarget, country_code: e.target.value.toUpperCase() })} placeholder="RU" maxLength={2} />
              </div>
            </div>
            <div className="input-group">
              <label className="input-label">Регион / Штат</label>
              <input className="input" value={editTarget.state} onChange={(e) => setEditTarget({ ...editTarget, state: e.target.value })} placeholder="Moscow" />
            </div>
            <div className="flex gap-6">
              <div className="flex items-center gap-3">
                <label className="switch">
                  <input type="checkbox" checked={editTarget.status} onChange={(e) => setEditTarget({ ...editTarget, status: e.target.checked })} />
                  <span className="switch-slider" />
                </label>
                <span style={{ fontWeight: 600 }}>Статус (вкл/выкл)</span>
              </div>
              <div className="flex items-center gap-3">
                <label className="switch">
                  <input type="checkbox" checked={editTarget.premium} onChange={(e) => setEditTarget({ ...editTarget, premium: e.target.checked })} />
                  <span className="switch-slider" />
                </label>
                <span style={{ fontWeight: 600 }}>Премиум</span>
              </div>
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        title="Удалить сервер?"
        message={<>AWG-сервер <b>{deleteTarget?.country}</b> ({deleteTarget?.ip_address}) будет удалён.</>}
        confirmText="Удалить"
        danger
        loading={saving}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
