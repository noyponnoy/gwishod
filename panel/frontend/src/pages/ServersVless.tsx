import { useState, useCallback, useEffect } from 'react';
import { vlessApi } from '../api/client';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { useToast } from '../context/ToastContext';
import { val, copyToClipboard } from '../utils/format';

interface VlessServer {
  server_ip: string;
  server_domain_port_path: string;
  server_domain_port_path_sub: string;
  login: string;
  password: string;
  session: string;
  t_name: number;
  description: string;
}

interface VlessForm {
  server_ip: string;
  server_domain_port_path: string;
  server_domain_port_path_sub: string;
  login: string;
  password: string;
  session: string;
  t_name: string;
  description: string;
}

const EMPTY: VlessForm = {
  server_ip: '', server_domain_port_path: '', server_domain_port_path_sub: '',
  login: '', password: '', session: '', t_name: '0', description: '',
};

// 8 полей VLESS-сервера.
const FIELDS: { key: keyof VlessForm; label: string; mono?: boolean; textarea?: boolean; hint?: string }[] = [
  { key: 'server_ip', label: 'IP-адрес сервера *', mono: true, hint: 'IP или домен Remnawave панели' },
  { key: 'server_domain_port_path', label: 'Домен:порт:путь', mono: true, hint: 'Основной адрес подключения' },
  { key: 'server_domain_port_path_sub', label: 'Sub домен:порт:путь', mono: true, hint: 'Адрес для подписки' },
  { key: 'login', label: 'Логин', mono: true, hint: 'Логин Remnawave панели' },
  { key: 'password', label: 'Пароль', mono: true, hint: 'Пароль Remnawave панели' },
  { key: 'session', label: 'Session', mono: true, hint: 'Сессионный ключ' },
  { key: 't_name', label: 'T-Name', hint: 'Число (идентификатор транспорта)' },
  { key: 'description', label: 'Описание', textarea: true },
];

export function ServersVless() {
  const toast = useToast();
  const [servers, setServers] = useState<VlessServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<{ open: boolean; mode: 'create' | 'edit'; form: VlessForm }>({
    open: false, mode: 'create', form: EMPTY,
  });
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<VlessServer | null>(null);
  const [viewTarget, setViewTarget] = useState<VlessServer | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await vlessApi.all();
      if (r.success) setServers(r.data || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => setModal({ open: true, mode: 'create', form: EMPTY });
  const openEdit = (s: VlessServer) => setModal({
    open: true, mode: 'edit',
    form: {
      server_ip: s.server_ip,
      server_domain_port_path: s.server_domain_port_path || '',
      server_domain_port_path_sub: s.server_domain_port_path_sub || '',
      login: s.login || '',
      password: s.password || '',
      session: s.session || '',
      t_name: String(s.t_name ?? 0),
      description: s.description || '',
    },
  });

  const handleSave = async () => {
    const f = modal.form;
    if (!f.server_ip.trim()) {
      toast.error('IP-адрес обязателен');
      return;
    }
    setSaving(true);
    try {
      const r = modal.mode === 'create'
        ? await vlessApi.create({ ...f })
        : await vlessApi.update({ ...f });
      if (r.success) {
        toast.success(modal.mode === 'create' ? 'Сервер создан' : 'Сервер обновлён');
        setModal({ ...modal, open: false });
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
      const r = await vlessApi.delete(deleteTarget.server_ip);
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

  const update = (key: keyof VlessForm, value: string) =>
    setModal((m) => ({ ...m, form: { ...m.form, [key]: value } }));

  const handleCopy = async (text: string) => {
    if (await copyToClipboard(text)) toast.info('Скопировано');
  };

  return (
    <div className="flex-col gap-6">
      <div className="page-header">
        <div>
          <div className="page-title">Серверы VLESS</div>
          <div className="page-subtitle">Remnawave панель · {servers.length} серверов</div>
        </div>
        <button className="btn btn-primary" onClick={openCreate}>
          <Icon name="plus" size={18} /> Добавить сервер
        </button>
      </div>

      <div className="card">
        <div className="card-body card-body-flush">
          {loading ? (
            <div className="loading-center"><span className="spinner" /> Загрузка…</div>
          ) : servers.length === 0 ? (
            <div className="empty-state">
              <Icon name="serverVless" size={48} className="empty-state-icon" />
              <div className="empty-state-title">Серверов нет</div>
              <button className="btn btn-primary mt-4" onClick={openCreate}>Добавить первый сервер</button>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="table table-mobile">
                <thead>
                  <tr>
                    <th>IP / Домен</th>
                    <th>Описание</th>
                    <th>Логин</th>
                    <th>T-Name</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {servers.map((s) => (
                    <tr key={s.server_ip}>
                      <td data-label="IP / Домен">
                        <div className="flex-col gap-1">
                          <span className="mono" style={{ fontWeight: 600 }}>{s.server_ip}</span>
                          <span className="mono text-muted truncate" style={{ maxWidth: 200, fontSize: 12 }}>{val(s.server_domain_port_path, '—')}</span>
                        </div>
                      </td>
                      <td data-label="Описание">{val(s.description, '—')}</td>
                      <td data-label="Логин" className="mono text-muted">{val(s.login, '—')}</td>
                      <td data-label="T-Name">{s.t_name}</td>
                      <td data-label="" className="col-actions">
                        <div className="flex gap-1 justify-end">
                          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setViewTarget(s)} title="Карточка">
                            <Icon name="eye" size={16} />
                          </button>
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

      {/* Карточка просмотра */}
      <Modal
        open={!!viewTarget}
        onClose={() => setViewTarget(null)}
        title="Карточка сервера VLESS"
        size="lg"
        footer={<button className="btn btn-secondary" onClick={() => setViewTarget(null)}>Закрыть</button>}
      >
        {viewTarget && (
          <div className="detail-grid">
            {([
              ['IP-адрес', viewTarget.server_ip, true],
              ['Домен:порт:путь', viewTarget.server_domain_port_path, true],
              ['Sub домен:порт:путь', viewTarget.server_domain_port_path_sub, true],
              ['Логин', viewTarget.login, true],
              ['Пароль', viewTarget.password, true],
              ['Session', viewTarget.session, true],
              ['T-Name', String(viewTarget.t_name), false],
              ['Описание', viewTarget.description, false],
            ] as const).map(([label, value, isMono]) => (
              <div key={label} className="detail-item">
                <span className="detail-label">{label}</span>
                <div className="flex items-center gap-2">
                  <span className={`detail-value ${isMono ? 'mono' : ''}`} style={{ flex: 1, minWidth: 0 }}>
                    <span className="truncate" style={{ display: 'inline-block', maxWidth: '100%' }} title={String(value)}>{val(String(value))}</span>
                  </span>
                  {value && value !== '0' && (
                    <button className="btn btn-ghost btn-icon btn-sm" onClick={() => handleCopy(String(value))} title="Копировать">
                      <Icon name="copy" size={14} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Modal>

      {/* Create / Edit */}
      <Modal
        open={modal.open}
        onClose={() => setModal({ ...modal, open: false })}
        title={modal.mode === 'create' ? 'Новый сервер VLESS' : 'Редактирование сервера'}
        size="lg"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setModal({ ...modal, open: false })}>Отмена</button>
            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
              {saving && <span className="spinner" style={{ width: 16, height: 16 }} />}
              {modal.mode === 'create' ? 'Создать' : 'Сохранить'}
            </button>
          </>
        }
      >
        <div className="detail-grid">
          {FIELDS.map((f) => (
            <div key={f.key} className="input-group">
              <label className="input-label">{f.label}</label>
              {f.textarea ? (
                <textarea className="textarea" value={modal.form[f.key]} onChange={(e) => update(f.key, e.target.value)} />
              ) : (
                <input
                  className={`input ${f.mono ? 'mono' : ''}`}
                  value={modal.form[f.key]}
                  onChange={(e) => update(f.key, e.target.value)}
                  disabled={modal.mode === 'edit' && f.key === 'server_ip'}
                />
              )}
              {f.hint && <span className="input-hint">{f.hint}</span>}
            </div>
          ))}
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        title="Удалить сервер?"
        message={<>Сервер <b>{deleteTarget?.server_ip}</b> будет удалён безвозвратно.</>}
        confirmText="Удалить"
        danger
        loading={saving}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
