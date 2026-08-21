// GW API client for the web panel — mirrors awgApi in the same file.
//
// Add this object to panel/frontend/src/api/client.ts (next to `awgApi`):

import { proxyGet, proxyPost } from './proxy'; // adjust import to whatever the file already uses

export interface GwServer {
  id?: string;
  name?: string;
  ip_address: string;
  ssh_port: number;
  ssh_username: string;
  ssh_password: string;
  proxy_host: string;
  proxy_port: number;
  proxy_scheme: 'http' | 'https';
  payload: string;
  sni?: string;
  ssh_hostkey?: string;
  country?: string;
  country_code?: string;
  state?: string;
  premium: boolean;
  recommend?: boolean;
  priority: number;
  status: boolean;
}

export const gwApi = {
  all: () => proxyGet('servers_gw/all'),
  get: (server_ip: string) => proxyGet('servers_gw/get', { server_ip }),
  create: (fields: Partial<GwServer>) => proxyPost('servers_gw/create', fields),
  update: (fields: Partial<GwServer> & { ip_address: string }) => proxyPost('servers_gw/update', fields),
  delete: (ip_address: string) => proxyPost('servers_gw/delete', { ip_address }),
};
