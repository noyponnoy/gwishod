import { useState, useCallback, useEffect } from 'react';
import { tariffsApi } from '../api/client';
import { Icon } from '../components/Icon';
import { Modal } from '../components/Modal';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { useToast } from '../context/ToastContext';
import { val } from '../utils/format';

interface Tariff {
  name: string; technicalName: string; description: string;
  price: number; enabled: boolean; duration: number;
}

interface TariffForm {
  name: string; technicalName: string; description: string;
  price: string; duration: string; enabled: boolean;
}

const EMPTY: TariffForm = {
  name: '', technicalName: '', description: '',
  price: '0', duration: '30', enabled: true,
};

export function Tariffs() {
  const toast = useToast();
  const [tariffs, setTariffs] = useState<Tariff[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<{ open: boolean; mode: 'create' | 'edit'; form: TariffForm }>({
    open: false, mode: 'create', form: EMPTY,
  });
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Tariff | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await tariffsApi.all();
      if (r.success) setTariffs(r.data || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => setModal({ open: true, mode: 'create', form: EMPTY });
  const openEdit = (t: Tariff) => setModal({
    open: true, mode: 'edit',
    form: {
      name: t.name, technicalName: t.technicalName, description: t.description || '',
      price: String(t.price), duration: String(t.duration), enabled: t.enabled,
    },
  });

  const handleSave = async () => {
    const f = modal.form;
    if (!f.name.trim() || !f.technicalName.trim()) {
      toast.error('Заполните обязательные поля', 'Название и тех. имя обязательны');
      return;
    }
    setSaving(true);
    try {
      const fields: Record<string, string> = {
        name: f.name,
        technicalName: f.technicalName,
        description: f.description,
        price: f.price,
        duration: f.duration,
        enabled: String(f.enabled),
      };
      const r = modal.mode === 'create'
        ? await tariffsApi.create(fields)
        : await tariffsApi.update(fields);
      if (r.success) {
        toast.success(modal.mode === 'create' ? 'Тариф создан' : 'Тариф обновлён');
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
      const r = await tariffsApi.delete(deleteTarget.technicalName);
      if (r.success) {
        toast.success('Тариф удалён');
        setDeleteTarget(null);
        load();
      } else {
        toast.error('Ошибка', r.message);
      }
    } finally {
      setSaving(false);
    }
  };

  const update = (key: keyof TariffForm, value: string | boolean) =>
    setModal((m) => ({ ...m, form: { ...m.form, [key]: value } }));

  return (
    <div className="flex-col gap-6">
      <div className="page-header">
        <div>
          <div className="page-title">Тарифы</div>
          <div className="page-subtitle">Управление подписками</div>
        </div>
        <button className="btn btn-primary" onClick={openCreate}>
          <Icon name="plus" size={18} /> Создать тариф
        </button>
      </div>

      <div className="card">
        <div className="card-body card-body-flush">
          {loading ? (
            <div className="loading-center"><span className="spinner" /> Загрузка…</div>
          ) : tariffs.length === 0 ? (
            <div className="empty-state">
              <Icon name="tariff" size={48} className="empty-state-icon" />
              <div className="empty-state-title">Тарифов нет</div>
              <button className="btn btn-primary mt-4" onClick={openCreate}>Создать первый тариф</button>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="table table-mobile">
                <thead>
                  <tr>
                    <th>Название</th>
                    <th>Тех. имя</th>
                    <th>Описание</th>
                    <th>Цена</th>
                    <th>Длительность</th>
                    <th>Статус</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {tariffs.map((t) => (
                    <tr key={t.technicalName}>
                      <td data-label="Название" style={{ fontWeight: 600 }}>{val(t.name)}</td>
                      <td data-label="Тех. имя" className="mono text-muted">{val(t.technicalName)}</td>
                      <td data-label="Описание" className="text-secondary truncate" style={{ maxWidth: 200 }}>{val(t.description, '—')}</td>
                      <td data-label="Цена" className="mono">{t.price} ₽</td>
                      <td data-label="Длительность">{t.duration} с.</td>
                      <td data-label="Статус">
                        {t.enabled
                          ? <span className="badge badge-success">Включён</span>
                          : <span className="badge badge-neutral">Выключен</span>}
                      </td>
                      <td data-label="" className="col-actions">
                        <div className="flex gap-1 justify-end">
                          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => openEdit(t)} title="Редактировать">
                            <Icon name="edit" size={16} />
                          </button>
                          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setDeleteTarget(t)} title="Удалить" style={{ color: 'var(--danger-fg)' }}>
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

      {/* Модалка create/edit */}
      <Modal
        open={modal.open}
        onClose={() => setModal({ ...modal, open: false })}
        title={modal.mode === 'create' ? 'Новый тариф' : 'Редактирование тарифа'}
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
        <div className="flex-col gap-4">
          <div className="input-group">
            <label className="input-label">Название *</label>
              <input className="input" value={modal.form.name} onChange={(e) => update('name', e.target.value)} placeholder="1 месяц Премиум" />
          </div>
          <div className="input-group">
            <label className="input-label">Техническое имя *</label>
            <input
              className="input mono"
              value={modal.form.technicalName}
              onChange={(e) => update('technicalName', e.target.value)}
              placeholder="premium_1m"
              disabled={modal.mode === 'edit'}
            />
            {modal.mode === 'edit' && <span className="input-hint">Тех. имя нельзя изменить</span>}
          </div>
          <div className="input-group">
            <label className="input-label">Описание</label>
            <textarea className="textarea" value={modal.form.description} onChange={(e) => update('description', e.target.value)} placeholder="Подписка на 1 месяц" />
          </div>
          <div className="flex gap-4">
            <div className="input-group grow">
              <label className="input-label">Цена (₽)</label>
              <input className="input" type="number" step="0.01" value={modal.form.price} onChange={(e) => update('price', e.target.value)} />
            </div>
            <div className="input-group grow">
              <label className="input-label">Длительность (с.)</label>
              <input className="input" type="number" value={modal.form.duration} onChange={(e) => update('duration', e.target.value)} />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <label className="switch">
              <input type="checkbox" checked={modal.form.enabled} onChange={(e) => update('enabled', e.target.checked)} />
              <span className="switch-slider" />
            </label>
            <span style={{ fontWeight: 600 }}>Тариф включён</span>
          </div>
        </div>
      </Modal>

      {/* Удаление */}
      <ConfirmDialog
        open={!!deleteTarget}
        title="Удалить тариф?"
        message={<>Тариф <b>{deleteTarget?.name}</b> будет удалён безвозвратно.</>}
        confirmText="Удалить"
        danger
        loading={saving}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
