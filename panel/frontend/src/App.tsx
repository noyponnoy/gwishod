import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider } from './context/ToastContext';
import { Layout } from './components/Layout';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { Users } from './pages/Users';
import { UserCard } from './pages/UserCard';
import { Tariffs } from './pages/Tariffs';
import { Invoices } from './pages/Invoices';
import { ServersIkev2 } from './pages/ServersIkev2';
import { ServersVless } from './pages/ServersVless';
import { ServersAwg } from './pages/ServersAwg';
import ServersGw from './pages/ServersGw';
import { Settings } from './pages/Settings';

function Protected({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div className="loading-center" style={{ minHeight: '100vh' }}>
        <span className="spinner spinner-lg" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <Layout>{children}</Layout>;
}

function AppRoutes() {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="loading-center" style={{ minHeight: '100vh' }}>
        <span className="spinner spinner-lg" />
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/users" element={<Protected><Users /></Protected>} />
      <Route path="/users/:deviceId" element={<Protected><UserCard /></Protected>} />
      <Route path="/tariffs" element={<Protected><Tariffs /></Protected>} />
      <Route path="/invoices" element={<Protected><Invoices /></Protected>} />
      <Route path="/servers/ikev2" element={<Protected><ServersIkev2 /></Protected>} />
      <Route path="/servers/vless" element={<Protected><ServersVless /></Protected>} />
      <Route path="/servers/awg" element={<Protected><ServersAwg /></Protected>} />
      <Route path="/servers/gw" element={<Protected><ServersGw /></Protected>} />
      <Route path="/settings" element={<Protected><Settings /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
