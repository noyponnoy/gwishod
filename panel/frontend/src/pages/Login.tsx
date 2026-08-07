import { useState, useEffect, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Icon } from '../components/Icon';

/** Telegram WebApp API (есть только внутри клиента Telegram). */
declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData: string;
        ready: () => void;
        expand: () => void;
        colorScheme?: string;
      };
    };
  }
}

export function Login() {
  const { login, loginTelegram, user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [tgTrying, setTgTrying] = useState(false);

  // Уже залогинен — на дашборд
  useEffect(() => {
    if (!authLoading && user) {
      navigate('/', { replace: true });
    }
  }, [authLoading, user, navigate]);

  // Авто-вход из Telegram WebApp (кнопка Menu / «Открыть веб-панель»)
  useEffect(() => {
    if (authLoading || user) return;

    const tg = window.Telegram?.WebApp;
    if (!tg?.initData) return;

    let cancelled = false;
    (async () => {
      setTgTrying(true);
      setError('');
      try {
        tg.ready?.();
        tg.expand?.();
      } catch {
        /* ignore */
      }
      const result = await loginTelegram(tg.initData);
      if (cancelled) return;
      setTgTrying(false);
      if (result.ok) {
        navigate('/', { replace: true });
      } else {
        setError(result.error || 'Не удалось войти через Telegram');
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authLoading, user, loginTelegram, navigate]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    setError('');
    setLoading(true);
    const ok = await login(username.trim(), password);
    setLoading(false);
    if (ok) {
      navigate('/');
    } else {
      setError('Неверный логин или пароль');
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <img src="favicon.png" alt="GW VPN" />
        </div>
        <h1 className="login-title">GW VPN Android</h1>
        <p className="login-sub">
          {tgTrying
            ? 'Вход через Telegram…'
            : 'Авторизуйтесь в панели администратора'}
        </p>

        {error && <div className="login-error">{error}</div>}

        {tgTrying ? (
          <div className="flex-col items-center gap-3" style={{ padding: '24px 0' }}>
            <span className="spinner spinner-lg" />
            <span className="text-muted" style={{ fontSize: 14 }}>
              Проверяем ваш Telegram ID…
            </span>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex-col gap-4">
            <div className="input-group">
              <label className="input-label" htmlFor="username">Логин</label>
              <input
                id="username"
                className="input"
                type="text"
                autoComplete="username"
                placeholder="admin"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
              />
            </div>

            <div className="input-group">
              <label className="input-label" htmlFor="password">Пароль</label>
              <div className="input-row">
                <input
                  id="password"
                  className="input"
                  type={showPwd ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="input-icon"
                  onClick={() => setShowPwd(!showPwd)}
                  aria-label="Показать пароль"
                  style={{ background: 'none', border: 'none', cursor: 'pointer' }}
                >
                  <Icon name={showPwd ? 'eyeOff' : 'eye'} size={18} />
                </button>
              </div>
            </div>

            <button type="submit" className="btn btn-primary btn-block" disabled={loading} style={{ height: 46, marginTop: 4 }}>
              {loading ? <span className="spinner" /> : 'Войти'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
