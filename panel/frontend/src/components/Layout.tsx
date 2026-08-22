import { useState, type ReactNode } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { Icon, type IconName } from './Icon';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { useEffect, useRef } from 'react';
import { monitorApi } from '../api/client';

interface NavItemDef {
  to: string;
  icon: IconName;
  label: string;
  group?: string;
}

const NAV: NavItemDef[] = [
  { to: '/', icon: 'dashboard', label: 'Аналитика' },
  { to: '/users', icon: 'users', label: 'Пользователи' },
  { to: '/tariffs', icon: 'tariff', label: 'Тарифы' },
  { to: '/invoices', icon: 'invoice', label: 'Платежи' },
  { to: '/servers/ikev2', icon: 'serverIkev2', label: 'IKEv2', group: 'servers' },
  { to: '/servers/vless', icon: 'serverVless', label: 'VLESS', group: 'servers' },
  { to: '/servers/awg', icon: 'serverAwg', label: 'AWG', group: 'servers' },
  { to: '/servers/gw', icon: 'serverGw', label: 'GW', group: 'servers' },
  { to: '/settings', icon: 'settings', label: 'Настройки' },
];

// Элементы для нижней мобиль-навигации (максимум 5).
const BOTTOM_NAV: NavItemDef[] = [
  { to: '/', icon: 'dashboard', label: 'Главная' },
  { to: '/users', icon: 'users', label: 'Юзеры' },
  { to: '/servers/ikev2', icon: 'serverIkev2', label: 'Серверы' },
  { to: '/tariffs', icon: 'tariff', label: 'Тарифы' },
  { to: '/settings', icon: 'settings', label: 'Ещё' },
];

function getPageTitle(pathname: string): string {
  const found = NAV.find((n) => n.to === pathname || (n.to !== '/' && pathname.startsWith(n.to)));
  if (found) return found.label;
  if (pathname.startsWith('/servers/')) return 'Серверы';
  return 'Центр управления API';
}

export function Layout({ children }: { children: ReactNode }) {
  const { theme, toggle } = useTheme();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [apiUp, setApiUp] = useState<boolean | null>(null);

  // Проверка статуса API для индикатора в topbar.
  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        const s = await monitorApi.status();
        if (active) setApiUp(s.isUp);
      } catch {
        if (active) setApiUp(false);
      }
    };
    check();
    const t = setInterval(check, 60000);
    return () => { active = false; clearInterval(t); };
  }, []);

  // Закрытие drawer при смене роута.
  useEffect(() => { setSidebarOpen(false); }, [location.pathname]);

  // Swipe-to-close sidebar
  const touchStartX = useRef(0);
  const touchStartY = useRef(0);
  useEffect(() => {
    if (!sidebarOpen) return;
    const onStart = (e: TouchEvent) => {
      touchStartX.current = e.touches[0].clientX;
      touchStartY.current = e.touches[0].clientY;
    };
    const onEnd = (e: TouchEvent) => {
      const dx = e.changedTouches[0].clientX - touchStartX.current;
      const dy = Math.abs(e.changedTouches[0].clientY - touchStartY.current);
      if (dx < -60 && dy < 80) setSidebarOpen(false);
    };
    document.addEventListener('touchstart', onStart, { passive: true });
    document.addEventListener('touchend', onEnd, { passive: true });
    return () => {
      document.removeEventListener('touchstart', onStart);
      document.removeEventListener('touchend', onEnd);
    };
  }, [sidebarOpen]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const NavList = ({ items }: { items: NavItemDef[] }) => (
    <>
      {items.map((item, i) => {
        const showLabel = item.group === 'servers' && items[i - 1]?.group !== 'servers';
        return (
          <div key={item.to}>
            {showLabel && <div className="nav-section-label">Серверы</div>}
            <NavLink
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <span className="nav-item-icon"><Icon name={item.icon} size={20} /></span>
              <span>{item.label}</span>
            </NavLink>
          </div>
        );
      })}
    </>
  );

  return (
    <div className="app-shell">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="mobile-overlay show" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-logo">
            <img src="/favicon.png" alt="GW VPN" />
          </div>
          <div className="brand-text">
            <div className="brand-name">GW VPN</div>
            <div className="brand-sub">Центр управления API</div>
          </div>
        </div>
        <nav className="sidebar-nav">
          <NavList items={NAV} />
        </nav>
        <div className="sidebar-footer">
          <div className="avatar avatar-sm">{(user || '?')[0].toUpperCase()}</div>
          <div className="sidebar-user">
            <div className="sidebar-user-name truncate">{user || '—'}</div>
            <div className="sidebar-user-role">Администратор</div>
          </div>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={handleLogout} title="Выйти">
            <Icon name="logout" size={18} />
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="main-area">
        <header className="topbar">
          <button
            className="btn btn-ghost btn-icon mobile-only"
            onClick={() => setSidebarOpen(true)}
            aria-label="Меню"
          >
            <Icon name="menu" size={22} />
          </button>
          <div className="topbar-title">
            {getPageTitle(location.pathname)}
            <span className="crumb desktop-only"> · GW VPN Android</span>
          </div>
          <div className="topbar-actions">
            {apiUp !== null && (
              <div className={`api-status ${apiUp ? 'up' : 'down'}`}>
                <span className="pulse-dot" />
                <span className="desktop-only">API {apiUp ? 'онлайн' : 'офлайн'}</span>
              </div>
            )}
            <button
              className="btn btn-ghost btn-icon"
              onClick={toggle}
              title={theme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
              aria-label="Переключить тему"
            >
              <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={20} />
            </button>
          </div>
        </header>

        <main className="page-content">{children}</main>
      </div>

      {/* Bottom nav (mobile) */}
      <nav className="bottom-nav">
        <div className="bottom-nav-items">
          {BOTTOM_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => `bn-item ${isActive ? 'active' : ''}`}
            >
              <Icon name={item.icon} size={22} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
