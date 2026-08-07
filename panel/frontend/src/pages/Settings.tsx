import { useState, useCallback, useEffect } from 'react';
import { authApi } from '../api/client';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { useToast } from '../context/ToastContext';
import { useAuth } from '../context/AuthContext';

interface Admin {
  username: string;
}

export function Settings() {
  const toast = useToast();
  const { user } = useAuth();
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [loading, setLoading] = useState(true);

  const [addModal, setAddModal] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [saving, setSaving] = useState(false);

  const [pwdModal, setPwdModal] = useState(false);
  const [oldPwd, setOldPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [newPwd2, setNewPwd2] = useState('');

  const [deleteTarget, setDeleteTarget] = useState<Admin | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authApi.listAdmins();
      setAdmins(r.admins || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    if (!newUsername.trim() || !newPassword) {
      toast.error('Заполните все поля');
      return;
    }
    if (newPassword.length < 8) {
      toast.error('Пароль слишком короткий', 'Минимум 8 символов');
      return;
    }
    setSaving(true);
    try {
      const r = await authApi.addAdmin(newUsername.trim(), newPassword);
      if (r.success) {
        toast.success('Админ добавлен', newUsername.trim());
        setAddModal(false);
        setNewUsername('');
        setNewPassword('');
        load();
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Ошибка';
      toast.error('Не удалось добавить', msg);
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (!oldPwd || !newPwd) {
      toast.error('Заполните все поля');
      return;
    }
    if (newPwd !== newPwd2) {
      toast.error('Пароли не совпадают');
      return;
    }
    if (newPwd.length < 8) {
      toast.error('Пароль слишком короткий', 'Минимум 8 символов');
      return;
    }
    setSaving(true);
    try {
      await authApi.changePassword(oldPwd, newPwd);
      toast.success('Пароль изменён');
      setPwdModal(false);
      setOldPwd('');
      setNewPwd('');
      setNewPwd2('');
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Ошибка';
      toast.error('Не удалось сменить пароль', msg);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setSaving(true);
    try {
      await authApi.removeAdmin(deleteTarget.username);
      toast.success('Админ удалён', deleteTarget.username);
      setDeleteTarget(null);
      load();
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Ошибка';
      toast.error('Не удалось удалить', msg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex-col gap-6">
      <div className="page-header">
        <div>
          <div className="page-title">Настройки</div>
          <div className="page-subtitle">Администраторы панели</div>
        </div>
      </div>

      {/* Текущий профиль */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Мой профиль</div>
        </div>
        <div className="card-body flex items-center gap-4 wrap">
          <span className="avatar avatar-lg">{(user || '?')[0].toUpperCase()}</span>
          <div className="grow">
            <div style={{ fontSize: 18, fontWeight: 700 }}>{user}</div>
            <div className="text-muted">Администратор панели</div>
          </div>
          <button className="btn btn-secondary" onClick={() => setPwdModal(true)}>
            <Icon name="shield" size={18} /> Сменить пароль
          </button>
        </div>
      </div>

      {/* Админы */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Администраторы ({admins.length})</div>
          <button className="btn btn-primary btn-sm" onClick={() => setAddModal(true)}>
            <Icon name="plus" size={16} /> Добавить
          </button>
        </div>
        <div className="card-body card-body-flush">
          {loading ? (
            <div className="loading-center"><span className="spinner" /> Загрузка…</div>
          ) : (
            <div className="table-wrap">
              <table className="table table-mobile">
                <thead>
                  <tr>
                    <th>Логин</th>
                    <th>Это вы</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {admins.map((a) => (
                    <tr key={a.username}>
                      <td data-label="Логин">
                        <div className="flex items-center gap-2">
                          <span className="avatar avatar-sm">{a.username[0].toUpperCase()}</span>
                          <span style={{ fontWeight: 600 }}>{a.username}</span>
                        </div>
                      </td>
                      <td data-label="Это вы">
                        {a.username === user
                          ? <span className="badge badge-accent">Вы</span>
                          : <span className="text-muted">—</span>}
                      </td>
                      <td data-label="" className="col-actions">
                        {a.username !== user && (
                          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setDeleteTarget(a)} title="Удалить" style={{ color: 'var(--danger-fg)' }}>
                            <Icon name="trash" size={16} />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Информация */}
      <div className="card">
        <div className="card-body flex gap-3" style={{ background: 'var(--info-bg)', borderRadius: 'var(--radius-lg)' }}>
          <Icon name="cloud" size={20} style={{ color: 'var(--info)', flexShrink: 0, marginTop: 2 }} />
          <div style={{ fontSize: 14, color: 'var(--fg-secondary)', lineHeight: 1.6 }}>
            Изменения в данных пользователей, серверов и тарифов
            мгновенно видны и в боте, и на сайте.
          </div>
        </div>
      </div>

      {/* Добавить админа */}
      <Modal
        open={addModal}
        onClose={() => setAddModal(false)}
        title="Новый администратор"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setAddModal(false)}>Отмена</button>
            <button className="btn btn-primary" onClick={handleAdd} disabled={saving}>
              {saving && <span className="spinner" style={{ width: 16, height: 16 }} />}
              Добавить
            </button>
          </>
        }
      >
        <div className="flex-col gap-4">
          <div className="input-group">
            <label className="input-label">Логин</label>
            <input className="input" value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="admin2" />
          </div>
          <div className="input-group">
            <label className="input-label">Пароль</label>
            <input className="input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="••••••••" />
            <span className="input-hint">Минимум 8 символов</span>
          </div>
        </div>
      </Modal>

      {/* Смена пароля */}
      <Modal
        open={pwdModal}
        onClose={() => setPwdModal(false)}
        title="Смена пароля"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setPwdModal(false)}>Отмена</button>
            <button className="btn btn-primary" onClick={handleChangePassword} disabled={saving}>
              {saving && <span className="spinner" style={{ width: 16, height: 16 }} />}
              Изменить
            </button>
          </>
        }
      >
        <div className="flex-col gap-4">
          <div className="input-group">
            <label className="input-label">Текущий пароль</label>
            <input className="input" type="password" value={oldPwd} onChange={(e) => setOldPwd(e.target.value)} />
          </div>
          <div className="input-group">
            <label className="input-label">Новый пароль</label>
            <input className="input" type="password" value={newPwd} onChange={(e) => setNewPwd(e.target.value)} />
          </div>
          <div className="input-group">
            <label className="input-label">Повторите новый пароль</label>
            <input className="input" type="password" value={newPwd2} onChange={(e) => setNewPwd2(e.target.value)} />
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={!!deleteTarget}
        title="Удалить администратора?"
        message={<>Администратор <b>{deleteTarget?.username}</b> потеряет доступ к панели.</>}
        confirmText="Удалить"
        danger
        loading={saving}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
