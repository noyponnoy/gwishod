import { useEffect, useState } from 'react';
import { gwApi, GwServer } from '../api/gwApi';

// GW servers admin page — mirrors ServersAwg.tsx structure.
// Add a route in App.tsx:  <Route path="/servers/gw" element={<Protected><ServersGw /></Protected>} />
// Add a nav item in Layout.tsx:  { to: '/servers/gw', icon: 'serverGw', label: 'GW', group: 'servers' }

const EMPTY: GwServer = {
  ip_address: '',
  ssh_port: 22,
  ssh_username: 'gw',
  ssh_password: '',
  proxy_host: '',
  proxy_port: 443,
  proxy_scheme: 'https',
  payload:
    'GET / HTTP/1.1[crlf]Host: [host][crlf]Connection: Upgrade[crlf]User-Agent: [ua][crlf]Upgrade: websocket[crlf][crlf]',
  sni: '',
  ssh_hostkey: '',
  country: '',
  country_code: '',
  state: '',
  premium: false,
  recommend: false,
  priority: 0,
  status: true,
};

export default function ServersGw() {
  const [servers, setServers] = useState<GwServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<GwServer | null>(null);
  const [creating, setCreating] = useState(false);

  const load = async () => {
    setLoading(true);
    const r = await gwApi.all();
    setServers(r?.servers ?? []);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const save = async (s: GwServer) => {
    if (creating) {
      await gwApi.create(s);
    } else {
      await gwApi.update({ ...s, ip_address: s.ip_address });
    }
    setEditing(null); setCreating(false);
    await load();
  };

  const toggle = async (s: GwServer) => {
    await gwApi.update({ ip_address: s.ip_address, status: !s.status });
    await load();
  };

  const remove = async (s: GwServer) => {
    if (!confirm(`Delete GW server ${s.ip_address}?`)) return;
    await gwApi.delete(s.ip_address);
    await load();
  };

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">🌐 GW Servers</h1>
        <button
          className="px-3 py-1.5 bg-blue-600 text-white rounded"
          onClick={() => { setEditing({ ...EMPTY }); setCreating(true); }}
        >+ Add</button>
      </div>

      {loading ? (
        <div>Loading…</div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b">
              <th className="py-2">Name</th>
              <th>SSH</th>
              <th>Proxy</th>
              <th>Country</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {servers.map((s) => (
              <tr key={s.ip_address} className="border-b hover:bg-gray-50">
                <td className="py-2">{s.name || s.country || s.ip_address}</td>
                <td>{s.ip_address}:{s.ssh_port}</td>
                <td>{s.proxy_host}:{s.proxy_port} ({s.proxy_scheme})</td>
                <td>{s.country} {s.country_code && `(${s.country_code})`}</td>
                <td>{s.status ? '🟢' : '🔴'}</td>
                <td className="space-x-2">
                  <button onClick={() => { setEditing(s); setCreating(false); }}>Edit</button>
                  <button onClick={() => toggle(s)}>{s.status ? 'Disable' : 'Enable'}</button>
                  <button onClick={() => remove(s)} className="text-red-600">Delete</button>
                </td>
              </tr>
            ))}
            {servers.length === 0 && (
              <tr><td colSpan={6} className="py-6 text-center text-gray-500">No GW servers yet</td></tr>
            )}
          </tbody>
        </table>
      )}

      {editing && (
        <GwEditor
          initial={editing}
          creating={creating}
          onSave={save}
          onCancel={() => { setEditing(null); setCreating(false); }}
        />
      )}
    </div>
  );
}

function GwEditor({ initial, creating, onSave, onCancel }: {
  initial: GwServer; creating: boolean; onSave: (s: GwServer) => void; onCancel: () => void;
}) {
  const [s, setS] = useState<GwServer>(initial);
  const set = (k: keyof GwServer, v: any) => setS({ ...s, [k]: v });

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onCancel}>
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-auto" onClick={e => e.stopPropagation()}>
        <h2 className="text-lg font-semibold mb-4">{creating ? 'Add GW server' : 'Edit GW server'}</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <Field label="Name" value={s.name || ''} onChange={v => set('name', v)} />
          <Field label="Country" value={s.country || ''} onChange={v => set('country', v)} />
          <Field label="Country code" value={s.country_code || ''} onChange={v => set('country_code', v)} />
          <Field label="City / state" value={s.state || ''} onChange={v => set('state', v)} />

          <Field label="SSH host (ip_address)" value={s.ip_address} onChange={v => set('ip_address', v)} disabled={!creating} />
          <Field label="SSH port" value={String(s.ssh_port)} onChange={v => set('ssh_port', parseInt(v) || 22)} />
          <Field label="SSH username" value={s.ssh_username} onChange={v => set('ssh_username', v)} />
          <Field label="SSH password" value={s.ssh_password} onChange={v => set('ssh_password', v)} />

          <Field label="Proxy host (CDN)" value={s.proxy_host} onChange={v => set('proxy_host', v)} />
          <Field label="Proxy port" value={String(s.proxy_port)} onChange={v => set('proxy_port', parseInt(v) || 80)} />
          <Select label="Proxy scheme" value={s.proxy_scheme} options={['http', 'https']} onChange={v => set('proxy_scheme', v)} />
          <Field label="SNI" value={s.sni || ''} onChange={v => set('sni', v)} />

          <Field label="Priority" value={String(s.priority)} onChange={v => set('priority', parseInt(v) || 0)} />
          <Field label="SSH hostkey (ed25519 pub, optional)" value={s.ssh_hostkey || ''} onChange={v => set('ssh_hostkey', v)} />
        </div>
        <div className="mt-3">
          <label className="block text-xs text-gray-500 mb-1">Payload (HTTP-injector template)</label>
          <textarea
            className="w-full border rounded p-2 font-mono text-xs"
            rows={4}
            value={s.payload}
            onChange={e => set('payload', e.target.value)}
          />
          <p className="text-xs text-gray-400 mt-1">
            Tokens: [host] [port] [protocol] [ua] [crlf] [cr] [lf] [crlf*2] [method] [ssh] [host_port]
          </p>
        </div>
        <div className="flex items-center gap-4 mt-3 text-sm">
          <label><input type="checkbox" checked={s.status} onChange={e => set('status', e.target.checked)} /> Enabled</label>
          <label><input type="checkbox" checked={!!s.premium} onChange={e => set('premium', e.target.checked)} /> Premium</label>
          <label><input type="checkbox" checked={!!s.recommend} onChange={e => set('recommend', e.target.checked)} /> Recommended</label>
        </div>
        <div className="flex justify-end gap-2 mt-5">
          <button className="px-4 py-2 border rounded" onClick={onCancel}>Cancel</button>
          <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={() => onSave(s)}>Save</button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, disabled }: { label: string; value: string; onChange: (v: string) => void; disabled?: boolean }) {
  return (
    <label className="block">
      <span className="block text-xs text-gray-500 mb-1">{label}</span>
      <input
        className="w-full border rounded p-2 disabled:bg-gray-100"
        value={value}
        disabled={disabled}
        onChange={e => onChange(e.target.value)}
      />
    </label>
  );
}

function Select({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <span className="block text-xs text-gray-500 mb-1">{label}</span>
      <select className="w-full border rounded p-2" value={value} onChange={e => onChange(e.target.value)}>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}
