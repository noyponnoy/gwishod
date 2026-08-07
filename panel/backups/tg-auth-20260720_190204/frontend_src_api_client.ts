import axios, { AxiosError } from 'axios';

/**
 * API-клиент панели.
 *
 * Все запросы идут на бекенд панели (FastAPI), который:
 *  - /api/auth/*   — авторизация (JWT в HttpOnly-cookie)
 *  - /api/proxy/*  — сквозной прокси к /vpn/api/v1/bot/* (main API)
 *  - /api/qr/decode — расшифровка QR
 *  - /api/monitor/status — статус API
 *
 * Cookie с JWT отправляется автоматически (withCredentials).
 */

const baseURL = (() => {
  const p = window.location.pathname;
  const m = p.match(/^(\/[^/]+)\/(login|$)/);
  return m ? m[1] : '';
})();

const http = axios.create({
  baseURL,
  withCredentials: true,
  timeout: 30000,
});

// Перехватчик: при 401 — редирект на логин.
http.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Не на странице логина — отправляем туда.
      if (!window.location.pathname.includes('/login')) {
        window.location.href = baseURL + '/login';
      }
    }
    return Promise.reject(error);
  },
);

// ─── Auth ──────────────────────────────────────────────────────
export const authApi = {
  login: (username: string, password: string) =>
    http.post('/api/auth/login', { username, password }).then((r) => r.data),
  logout: () => http.post('/api/auth/logout').then((r) => r.data),
  me: () => http.get('/api/auth/me').then((r) => r.data),
  listAdmins: () => http.get('/api/auth/admins').then((r) => r.data),
  addAdmin: (username: string, password: string) =>
    http.post('/api/auth/admins', { username, password }).then((r) => r.data),
  removeAdmin: (username: string) =>
    http.post('/api/auth/admins/remove', { username }).then((r) => r.data),
  changePassword: (old_password: string, new_password: string) =>
    http.post('/api/auth/password', { old_password, new_password }).then((r) => r.data),
};

// ─── Monitor ───────────────────────────────────────────────────
export const monitorApi = {
  status: () => http.get('/api/monitor/status').then((r) => r.data),
};

// ─── QR ────────────────────────────────────────────────────────
export const qrApi = {
  decode: (text: string) =>
    http.post('/api/qr/decode', { text }).then((r) => r.data),
};

// ─── Прокси к main API ─────────────────────────────────────────
// GET  → params передаются как query
// POST → тело { params?, json? } — бекенд сам кодирует form/json

export interface ProxyResult<T = any> {
  success: number;
  data?: T;
  total?: number;
  skip?: number;
  limit?: number;
  message?: string;
  [key: string]: any;
}

async function proxyGet<T = any>(path: string, params?: Record<string, any>): Promise<ProxyResult<T>> {
  const r = await http.get(`/api/proxy/${path}`, { params });
  return r.data;
}

async function proxyPost<T = any>(
  path: string,
  body?: Record<string, any>,
  params?: Record<string, any>,
): Promise<ProxyResult<T>> {
  const r = await http.post(`/api/proxy/${path}`, { json: body, params });
  return r.data;
}

// ─── Users ─────────────────────────────────────────────────────
export const usersApi = {
  // platform: '' | 'android' | 'ios' | 'unknown'
  all: (skip = 0, limit = 20, platform = '') =>
    proxyGet('users/all', { skip, limit, ...(platform ? { platform } : {}) }),
  get: (device_id: string) => proxyGet('users/get', { device_id }),
  search: (q: string, platform = '') =>
    proxyGet('users/search', { q, ...(platform ? { platform } : {}) }),
  searchByMnemonic: (mnemonic: string) => proxyGet('users/search_by_mnemonic', { mnemonic }),
  setPremium: (deviceId: string, days: number) =>
    proxyPost('users/premium/set', { deviceId, days: String(days) }),
  revokePremium: (deviceId: string) =>
    proxyPost('users/premium/revoke', { deviceId }),
};

// ─── Analytics ─────────────────────────────────────────────────
export const analyticsApi = {
  summary: () => proxyGet('analytics/summary'),
  serversStats: () => proxyGet('servers/stats'),
};

// ─── IKEv2 servers ─────────────────────────────────────────────
export const ikev2Api = {
  all: () => proxyGet('servers/all'),
  get: (ip_address: string) => proxyGet('servers/get', { ip_address }),
  create: (fields: Record<string, string>) => proxyPost('servers/create', fields),
  update: (fields: Record<string, string>) => proxyPost('servers/update', fields),
  delete: (ipAddress: string) => proxyPost('servers/delete', { ipAddress }),
  toggle: (ipAddress: string) => proxyPost('servers/toggle', { ipAddress }),
};

// ─── VLESS servers ─────────────────────────────────────────────
export const vlessApi = {
  all: () => proxyGet('servers_vless/all'),
  get: (server_ip: string) => proxyGet('servers_vless/get', { server_ip }),
  create: (fields: Record<string, string>) => proxyPost('servers_vless/create', fields),
  update: (fields: Record<string, string>) => proxyPost('servers_vless/update', fields),
  delete: (server_ip: string) => proxyPost('servers_vless/delete', { server_ip }),
};

// ─── AWG servers ───────────────────────────────────────────────
export const awgApi = {
  all: () => proxyGet('servers_awg/all'),
  get: (server_ip: string) => proxyGet('servers_awg/get', { server_ip }),
  create: (fields: Record<string, any>) => proxyPost('servers_awg/create', fields),
  update: (fields: Record<string, any>) => proxyPost('servers_awg/update', fields),
  delete: (ip_address: string) => proxyPost('servers_awg/delete', { ip_address }),
};

// ─── Tariffs ───────────────────────────────────────────────────
export const tariffsApi = {
  all: () => proxyGet('tariffs/all'),
  get: (technical_name: string) => proxyGet('tariffs/get', { technical_name }),
  create: (fields: Record<string, string>) => proxyPost('tariffs/create', fields),
  update: (fields: Record<string, string>) => proxyPost('tariffs/update', fields),
  delete: (technicalName: string) => proxyPost('tariffs/delete', { technicalName }),
};

// ─── Invoices ──────────────────────────────────────────────────
export const invoicesApi = {
  all: (skip = 0, limit = 20) => proxyGet('invoices/all', { skip, limit }),
};
