import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { usersApi, qrApi } from '../api/client';
import { Icon } from '../components/Icon';
import { useToast } from '../context/ToastContext';
import { fmtBytes, fmtDate, isPremiumActive, platformBadge, val } from '../utils/format';
import { decodeQrFromImage } from '../utils/qrScanner';

interface UserItem {
  id: string; email: string; isAnonymous: boolean; isPremium: boolean;
  premiumEnd: string; createdAt: string; lastLogin: string;
  totalUpload: number; totalDownload: number; countryCode: string;
  platform?: string; bundleId?: string; deviceId?: string;
}

type PlatformFilter = '' | 'android' | 'ios' | 'unknown';

const PAGE_SIZE = 20;

function compactMiddle(value: string, fallback = '—') {
  const text = val(value, fallback);
  return text.length > 6 ? `${text.slice(0, 3)}...${text.slice(-3)}` : text;
}

export function Users() {
  const navigate = useNavigate();
  const toast = useToast();
  const [users, setUsers] = useState<UserItem[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchMode, setSearchMode] = useState<'mnemonic' | 'qr'>('qr');
  const [searching, setSearching] = useState(false);
  // Фильтр по платформе (android / ios / unknown)
  const [platformFilter, setPlatformFilter] = useState<PlatformFilter>('');

  // Состояние режима QR: загрузка изображения.
  const [qrPreview, setQrPreview] = useState<string | null>(null);
  const [qrScanning, setQrScanning] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await usersApi.all(skip, PAGE_SIZE, platformFilter);
      if (r.success) {
        setUsers(r.data || []);
        setTotal(r.total || 0);
      }
    } finally {
      setLoading(false);
    }
  }, [skip, platformFilter]);

  useEffect(() => { load(); }, [load]);

  // Смена фильтра платформы — с первой страницы
  const setPlatform = (p: PlatformFilter) => {
    setPlatformFilter(p);
    setSkip(0);
  };

  const handleSearch = async () => {
    const q = searchQuery.trim();
    if (!q) { load(); return; }
    setSearching(true);
    try {
      const r = await usersApi.searchByMnemonic(q);
      if (r.success && r.data) {
        const deviceId = r.data.deviceId || r.data.device_id || r.data.id;
        if (deviceId) navigate(`/users/${deviceId}`);
        else toast.warn('Пользователь не найден');
      } else {
        // Если юзер не найден, но есть deviceId — покажем его.
        if (r.deviceId) {
          toast.info('Пользователь не найден', `Device ID: ${r.deviceId}`);
          navigate(`/users/${r.deviceId}`);
        } else {
          toast.error('Не найдено', r.message);
        }
      }
    } catch (e: any) {
      toast.error('Ошибка поиска', e?.message);
    } finally {
      setSearching(false);
    }
  };

  const handleReset = () => {
    setSearchQuery('');
    setPlatformFilter('');
    setSkip(0);
    load();
  };

  // ─── Распознавание QR с изображения ──────────────────────────
  const handleQrImage = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      toast.error('Нужен файл изображения', 'Выберите PNG, JPG или другой формат картинки');
      return;
    }
    // Превью.
    const previewUrl = URL.createObjectURL(file);
    setQrPreview(previewUrl);
    setQrScanning(true);
    setSearching(true);
    try {
      // 1) Распознаём QR прямо в браузере через jsQR.
      const rawText = await decodeQrFromImage(file);
      if (!rawText) {
        toast.error('QR не найден на фото', 'Убедитесь, что QR-код виден и занимает большую часть кадра');
        return;
      }
      // 2) Отправляем распознанный текст на бекенд для расшифровки
      //    (RSA + AES — как в боте) и получения device-id.
      const decoded = await qrApi.decode(rawText);
      const deviceId = decoded.success ? decoded.deviceId : rawText.toUpperCase();
      // 3) Ищем пользователя по device-id.
      const r = await usersApi.get(deviceId);
      if (r.success && r.data) {
        toast.success('QR распознан', `Пользователь найден`);
        navigate(`/users/${deviceId}`);
      } else {
        toast.warn('Пользователь не найден', `Device ID: ${deviceId}`);
        navigate(`/users/${deviceId}`);
      }
    } catch (e: any) {
      toast.error('Ошибка распознавания', e?.message);
    } finally {
      setQrScanning(false);
      setSearching(false);
    }
  };

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleQrImage(f);
    // Сбрасываем input, чтобы можно было выбрать тот же файл повторно.
    e.target.value = '';
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleQrImage(f);
  };

  const onPaste = useCallback((e: ClipboardEvent) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        const f = items[i].getAsFile();
        if (f) {
          handleQrImage(f);
          e.preventDefault();
          break;
        }
      }
    }
  }, []);

  // В режиме QR слушаем вставку из буфера (Ctrl+V скриншота).
  useEffect(() => {
    if (searchMode !== 'qr') return;
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [searchMode, onPaste]);

  // Сброс превью при выходе из режима QR.
  useEffect(() => {
    if (searchMode !== 'qr' && qrPreview) {
      URL.revokeObjectURL(qrPreview);
      setQrPreview(null);
    }
  }, [searchMode, qrPreview]);

  const currentPage = Math.floor(skip / PAGE_SIZE) + 1;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="flex-col gap-6">
      <div className="page-header">
        <div>
          <div className="page-title">Пользователи</div>
          <div className="page-subtitle">Всего: {total}{platformFilter ? ` · фильтр: ${platformFilter}` : ''}</div>
        </div>
      </div>

      {/* Фильтр платформы */}
      <div className="card">
        <div className="card-body">
          <div className="tabs">
            <button className={`tab ${platformFilter === '' ? 'active' : ''}`} onClick={() => setPlatform('')}>Все</button>
            <button className={`tab ${platformFilter === 'android' ? 'active' : ''}`} onClick={() => setPlatform('android')}>Android</button>
            <button className={`tab ${platformFilter === 'ios' ? 'active' : ''}`} onClick={() => setPlatform('ios')}>iOS</button>
            <button className={`tab ${platformFilter === 'unknown' ? 'active' : ''}`} onClick={() => setPlatform('unknown')}>Неизвестно</button>
          </div>
        </div>
      </div>

      {/* Поиск */}
      <div className="card">
        <div className="card-body">
          <div className="tabs mb-4">
            <button className={`tab ${searchMode === 'qr' ? 'active' : ''}`} onClick={() => setSearchMode('qr')}>По QR-коду (фото)</button>
            <button className={`tab ${searchMode === 'mnemonic' ? 'active' : ''}`} onClick={() => setSearchMode('mnemonic')}>По мнемонике</button>
          </div>

          {searchMode === 'qr' ? (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={onFileChange}
              />
              <div
                className={`qr-dropzone ${dragOver ? 'dragover' : ''}`}
                onClick={() => !qrScanning && fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
              >
                {qrPreview ? (
                  qrScanning ? (
                    <div className="qr-scanning">
                      <img src={qrPreview} alt="QR" className="qr-preview" style={{ opacity: 0.5 }} />
                      <div className="scan-line" />
                      <span className="flex items-center gap-2">
                        <span className="spinner" style={{ width: 16, height: 16 }} />
                        Распознавание QR…
                      </span>
                    </div>
                  ) : (
                    <>
                      <img src={qrPreview} alt="QR" className="qr-preview" />
                      <div className="qr-dropzone-title">Готово</div>
                      <div className="qr-dropzone-hint">Нажмите, чтобы выбрать другое фото</div>
                    </>
                  )
                ) : (
                  <>
                    <div className="qr-dropzone-icon"><Icon name="qr" size={28} /></div>
                    <div className="qr-dropzone-title">Загрузите фото QR-кода</div>
                    <div className="qr-dropzone-hint">
                      Нажмите, перетащите файл или вставьте скриншот (Ctrl+V)
                    </div>
                  </>
                )}
              </div>
              <div className="input-hint mt-2">
                Приложите скриншот или фото QR-кода из приложения. Распознавание выполняется прямо в браузере, затем данные расшифровываются на сервере (RSA+AES, как в боте).
              </div>
            </>
          ) : (
            <>
              <div className="search-bar">
                  <input
                    className="input"
                    type="text"
                    placeholder="12 слов через пробел…"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                />
                <button className="btn btn-primary" onClick={handleSearch} disabled={searching}>
                  {searching ? <span className="spinner" style={{ width: 16, height: 16 }} /> : <Icon name="search" size={18} />}
                  Найти
                </button>
                <button className="btn btn-ghost" onClick={handleReset}>Сброс</button>
              </div>
              {searchMode === 'mnemonic' && (
                <div className="input-hint mt-2">Вбей фразу из 12 слов, а я подтяну данные пользователя.</div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Таблица */}
      <div className="card">
        <div className="card-body card-body-flush">
          {loading ? (
            <div className="loading-center"><span className="spinner" /> Загрузка…</div>
          ) : users.length === 0 ? (
            <div className="empty-state">
              <Icon name="users" size={48} className="empty-state-icon" />
              <div className="empty-state-title">Пользователи не найдены</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="table table-mobile">
                <thead>
                  <tr>
                    <th>Пользователь</th>
                    <th>Платформа</th>
                    <th>Премиум</th>
                    <th>Трафик</th>
                    <th>Последний вход</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => {
                    const deviceId = u.deviceId || u.id;
                    const premiumActive = isPremiumActive(u.premiumEnd, u.isPremium);
                    const traffic = fmtBytes(Number(u.totalUpload) + Number(u.totalDownload));
                    return (
                      <tr key={u.id} style={{ cursor: 'pointer' }} onClick={() => navigate(`/users/${deviceId}`)}>
                        <td data-label="Пользователь">
                          <div className="flex items-center gap-2">
                            <span className="avatar avatar-sm">{(u.id || '?')[0].toUpperCase()}</span>
                            <span className="mono truncate" style={{ maxWidth: 160 }} title={u.id}>{compactMiddle(u.id)}</span>
                          </div>
                        </td>
                        <td data-label="Платформа">
                          <span className="badge badge-neutral">{platformBadge(u.platform)}</span>
                        </td>
                        <td data-label="Премиум">
                          {premiumActive
                            ? <span className="badge badge-warn"><Icon name="star" size={11} /> Премиум</span>
                            : <span className="badge badge-neutral">Бесплатный</span>}
                        </td>
                        <td data-label="Трафик" className="mono">{traffic}</td>
                        <td data-label="Последний вход" className="text-muted">{fmtDate(u.lastLogin)}</td>
                        <td data-label="" className="col-actions">
                          <Icon name="chevronRight" size={18} className="text-muted" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Пагинация */}
        {users.length > 0 && (
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
