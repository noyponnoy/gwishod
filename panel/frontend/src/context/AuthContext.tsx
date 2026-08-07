import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { authApi } from '../api/client';

interface AuthCtx {
  user: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<boolean>;
  loginTelegram: (initData: string) => Promise<{ ok: boolean; error?: string }>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      const data = await authApi.me();
      setUser(data.username);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const login = async (username: string, password: string): Promise<boolean> => {
    try {
      const data = await authApi.login(username, password);
      if (data.success) {
        setUser(data.username);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  };

  const loginTelegram = async (initData: string): Promise<{ ok: boolean; error?: string }> => {
    try {
      const data = await authApi.loginTelegram(initData);
      if (data.success) {
        setUser(data.username);
        return { ok: true };
      }
      return { ok: false, error: data.detail || data.message || 'Ошибка входа' };
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      return { ok: false, error: typeof detail === 'string' ? detail : 'Нет доступа через Telegram' };
    }
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
    }
  };

  return (
    <Ctx.Provider value={{ user, loading, login, loginTelegram, logout, refresh }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
