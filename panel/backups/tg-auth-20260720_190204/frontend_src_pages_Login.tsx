import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Icon } from '../components/Icon';

export function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
          <img src="/favicon.png" alt="GW VPN" />
        </div>
        <h1 className="login-title">GW VPN Android</h1>
        <p className="login-sub">Авторизуйтесь в панели администратора</p>

        {error && <div className="login-error">{error}</div>}

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
      </div>
    </div>
  );
}
