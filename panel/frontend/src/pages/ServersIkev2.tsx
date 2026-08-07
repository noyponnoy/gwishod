import { useState, useCallback, useEffect } from 'react';
import { ikev2Api } from '../api/client';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { useToast } from '../context/ToastContext';
import { countryFlag, val } from '../utils/format';

interface Ikev2Server {
  id: string; country: string; countryCode: string; ipAddress: string;
  premium: boolean; status: boolean; state: string; recommend: boolean; priority: number;
}

export function ServersIkev2() {
  const toast = useToast();
  const [servers, setServers] = useState<Ikev2Server[]>([]);
  const [loading, setLoading] = useState(true);
  const [renameTarget, setRenameTarget] = useState<Ikev2Server | null>(null);
  const [renameCountry, setRenameCountry] = useState('');
  const [renameCode, setRenameCode] = useState('');
  const [renameState, setRenameState] = useState('');
  const [renamePremium, setRenamePremium] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Ikev2Server | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await ikev2Api.all();
      if (r.success) setServers(r.data || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleToggle = async (s: Ikev2Server) => {
    const r = await ikev2Api.toggle(s.ipAddress);
    if (r.success) {
      toast.success(s.status ? 'Сервер выключен' : 'Сервер включён');
      load();
    } else {
      toast.error('Ошибка', r.message);
    }
  };

  const handleTogglePremium = async (s: Ikev2Server) => {
    const r = await ikev2Api.update({
      ipAddress: s.ipAddress,
      premium: String(!s.premium),
    });
    if (r.success) {
      toast.success(s.premium ? 'Премиум снят — бесплатный' : 'Премиум включён');
      load();
    } else {
      toast.error('Ошибка', r.message);
    }
  };

  const openRename = (s: Ikev2Server) => {
    setRenameTarget(s);
    setRenameCountry(s.country || '');
    setRenameCode(s.countryCode || '');
    setRenameState(s.state || '');
    setRenamePremium(!!s.premium);
  };

  const handleRename = async () => {
    if (!renameTarget) return;
    setSaving(true);
    try {
      const r = await ikev2Api.update({
        ipAddress: renameTarget.ipAddress,
        country: renameCountry,
        countryCode: renameCode,
        state: renameState,
        premium: String(renamePremium),
      });
      if (r.success) {
        toast.success('Сервер обновлён');
        setRenameTarget(null);
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
      const r = await ikev2Api.delete(deleteTarget.ipAddress);
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
          <div className="page-title">Серверы IKEv2</div>
          <div className="page-subtitle">Всего: {servers.length}</div>
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
              <Icon name="serverIkev2" size={48} className="empty-state-icon" />
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
                    <th>Премиум</th>
                    <th>Приоритет</th>
                    <th>Статус</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {servers.map((s) => (
                    <tr key={s.ipAddress}>
                      <td data-label="Страна">
                        <div className="flex items-center gap-2">
                          <span style={{ fontSize: 18 }}>{countryFlag(s.countryCode)}</span>
                          <span style={{ fontWeight: 600 }}>{val(s.country, 'N/A')}</span>
                        </div>
                      </td>
                      <td data-label="IP-адрес" className="mono">{s.ipAddress}</td>
                      <td data-label="Регион" className="text-muted">{val(s.state, '—')}</td>
                      <td data-label="Премиум">
                        <div className="flex items-center gap-2">
                          <label className="switch" title={s.premium ? 'Сделать бесплатным' : 'Сделать премиум'}>
                            <input
                              type="checkbox"
                              checked={s.premium}
                              onChange={() => handleTogglePremium(s)}
                            />
                            <span className="switch-slider" />
                          </label>
                          {s.premium
                            ? <span className="badge badge-warn"><Icon name="star" size={11} /> Премиум</span>
                            : <span className="badge badge-neutral">Бесплатный</span>}
                        </div>
                      </td>
                      <td data-label="Приоритет">{s.priority}</td>
                      <td data-label="Статус">
                        <span className={`badge ${s.status ? 'badge-success' : 'badge-danger'}`}>
                          {s.status ? 'Включён' : 'Выключен'}
                        </span>
                      </td>
                      <td data-label="" className="col-actions">
                        <div className="flex gap-1 justify-end">
                          <label className="switch" title={s.status ? 'Выключить' : 'Включить'}>
                            <input type="checkbox" checked={s.status} onChange={() => handleToggle(s)} />
                            <span className="switch-slider" />
                          </label>
                          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => openRename(s)} title="Редактировать">
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

      {/* Rename / edit country + premium */}
      <Modal
        open={!!renameTarget}
        onClose={() => setRenameTarget(null)}
        title="Редактирование сервера"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setRenameTarget(null)}>Отмена</button>
            <button className="btn btn-primary" onClick={handleRename} disabled={saving}>
              {saving && <span className="spinner" style={{ width: 16, height: 16 }} />}
              Сохранить
            </button>
          </>
        }
      >
        <div className="flex-col gap-4">
          <div className="input-group">
            <label className="input-label">IP-адрес</label>
            <input className="input mono" value={renameTarget?.ipAddress || ''} disabled />
          </div>
          <div className="flex gap-4">
            <div className="input-group grow">
              <label className="input-label">Страна</label>
              <input className="input" value={renameCountry} onChange={(e) => setRenameCountry(e.target.value)} placeholder="Россия" />
            </div>
            <div className="input-group grow">
              <label className="input-label">Код страны</label>
              <input className="input mono" value={renameCode} onChange={(e) => setRenameCode(e.target.value.toUpperCase())} placeholder="RU" maxLength={2} />
            </div>
          </div>
          <div className="input-group">
            <label className="input-label">Регион</label>
            <input
              className="input"
              value={renameState}
              onChange={(e) => setRenameState(e.target.value)}
              placeholder="Moscow / EU / etc."
            />
          </div>
          <div className="flex items-center gap-3">
            <label className="switch">
              <input
                type="checkbox"
                checked={renamePremium}
                onChange={(e) => setRenamePremium(e.target.checked)}
              />
              <span className="switch-slider" />
            </label>
            <span style={{ fontWeight: 600 }}>
              {renamePremium ? 'Премиум' : 'Бесплатный'}
            </span>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        title="Удалить сервер?"
        message={<>Сервер <b>{deleteTarget?.country}</b> ({deleteTarget?.ipAddress}) будет удалён.</>}
        confirmText="Удалить"
        danger
        loading={saving}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
