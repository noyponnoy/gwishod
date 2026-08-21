# GW protocol — server side (gwishod)

This adds the **GW** transport (HTTP proxy + custom payload + SSH-over-CDN) to the
existing VPN platform: a VPS node installer, API endpoints, encrypted config delivery,
a Telegram-bot admin section, and a web-panel page.

> **What GW is:** a no-root-friendly tunnel where the Android client builds an SSH
> `direct-tcpip` SOCKS5 tunnel to a restricted VPS user, riding a Cloudflare-CDN-fronted
> HTTP/1.1 `101 Switching Protocols` upgrade (the "payload" injection). See the Android
> repo (`gwapk`, branch `feature/gw-protocol`) for the client.

---

## 1. VPS node installer — `vps/install.sh`

Runs on a fresh Debian/RHEL/Alpine VPS as root:

```bash
curl -sSL https://raw.githubusercontent.com/noyponnoy/gwishod/feature/gw-protocol/vps/install.sh -o gw-install.sh
sudo bash gw-install.sh --domain gw.example.com --ssh-port 22 --ws-port 80 -y
```

Options:
| Flag | Default | Meaning |
|---|---|---|
| `--ssh-port` | 22 | SSH listen port (the tunnel terminates here) |
| `--ws-port` | 80 | WebSocket / HTTP-101 bridge port (CDN connects here) |
| `--wss-port` | 443 | HTTPS variant (self-signed origin cert for Cloudflare Full) |
| `--domain` | — | FQDN for TLS / Cloudflare fronting |
| `--ssh-backend openssh\|dropbear` | openssh | dropbear is lighter for extreme concurrency |
| `--ws-backend node\|python` | node | python fallback if Node unavailable |
| `--gw-user` | gw | restricted system user |
| `--gw-pass` | auto | password (auto-generated if omitted) |
| `--no-firewall` / `--no-tuning` | — | skip nftables / sysctl |

What it does:
1. Installs OpenSSH (or dropbear) + Node (or Python) + nftables.
2. Applies kernel tuning for 5000+ concurrent connections
   (`fs.file-max`, `nf_conntrack_max`, `somaxconn`, `tcp_syn_backlog`, BBR, keepalive).
3. Creates a **locked-down `gw` user**: shell `/usr/sbin/nologin`, SSH `Match` block
   with `ForceCommand /bin/false`, `PermitTTY no`, `AllowTcpForwarding yes`,
   `PermitTunnel no`, `AllowAgentForwarding no`, `X11Forwarding no`,
   `AllowStreamLocalForwarding no`, `PermitOpen any`, `PermitListen none`.
   → the user can **only** open `direct-tcpip` forwarding channels. No shell, no SCP,
   no SFTP, no PTY, no tunnel device.
4. Installs the **WebSocket / HTTP-101 bridge** (`ws-bridge.js` / `ws-bridge.py`): on
   each connection it replies `HTTP/1.1 101 Switching Protocols\r\nContent-Length: <huge>\r\n\r\n`
   then bridges raw bytes to the local SSH port — exactly what the client's payload
   upgrade expects. Runs as a systemd unit `gw-ws-bridge`.
5. Configures **nftables**: allow admin SSH + WS bridge ports, drop other inbound.
6. Writes generated credentials to `/etc/gw-node/credentials.txt` (chmod 600) and a
   `gw-status` helper.

**Uninstall:** `sudo bash uninstall.sh -y` (or `--keep-user` to rotate the password only).

**Enter the credentials into the bot/API** via the new GW section (or the panel):
`proxy_host`, `proxy_port`, `ssh_host`, `ssh_port`, `ssh_username`, `ssh_password`,
`payload`, `sni`.

---

## 2. API — `api/src/...`

New files:
- `api/src/db/v3/gw/server_pojo.py` — `ServerPojo`, collection `servers_gw`.
  Fields: `id, name, ip_address(ssh host), ssh_port, ssh_username, ssh_password,
  proxy_host, proxy_port, proxy_scheme, payload, sni, ssh_hostkey, country,
  country_code, state, premium, recommend, priority, status, created_at, updated_at`.
- `api/src/endpoints/v3/gw/bot_api.py` — bot/panel CRUD:
  `GET /vpn/api/v1/bot/servers_gw/all`, `/get`, `POST /create`, `/update`, `/delete`.
- `api/src/endpoints/v3/gw/client.py` — `POST /vpn/api/v1/user/server_gw`
  (encrypted config delivery, protected by the existing `AndroidSignatureMiddleware`).
- `api/src/utils/crypto_gw.py` — ECIES envelope (secp256k1 ECDH + AES-256-GCM).

**Registration** (see `api/REGISTRATION_PATCH.md`): add two imports + two
`app.include_router(...)` calls in `api/src/endpoints/server.py`, and `coincurve` to
`api/requirements.txt`.

### Encrypted config delivery (security model)

`POST /vpn/api/v1/user/server_gw` receives the app user's secp256k1 public key and
returns, per enabled server, a public `meta` block (country/priority/etc.) **plus**
an ECIES `enc` envelope:
```
eph  = ephemeral secp256k1 pubkey (hex)
ct   = base64( AES-256-GCM( shared_secret, plaintext_config ) )
iv   = base64(12-byte nonce)
```
The client decrypts with its own secp256k1 private key (Android Keystore where
supported). **No symmetric key is embedded in the APK.** A passive network observer
sees only ciphertext; extracting one client's key reveals only that client's configs,
not a global secret or other users' configs.

**Honest limitation:** a client that can decrypt a config can also exfiltrate it. This
scheme raises the bar against mass harvesting but cannot stop a fully-compromised
client from leaking the specific creds it received. We further limit blast radius by
using a **small pool of shared SSH accounts per region** (not one global account) and
**rotating** them; rotating is a one-line `--gw-pass` change on the installer plus an
API update. See `SECURITY.md` (added with the client repo) for the full threat model.

---

## 3. Telegram bot — `bot/handlers/admin/servers_gw.py`

New GW section (button `🌐 GW` in `servers_menu()`). Capabilities:
- list servers (active/total)
- add server (one-line `name | ssh_host | ssh_port | ssh_user | ssh_pass | proxy_host | proxy_port | payload`)
- per-field edit: name, country, state, country_code, **ssh host/port/user/pass,
  proxy host/port/scheme, payload, sni, ssh hostkey, priority**
- enable/disable, premium toggle, delete

**Registration:** see `bot/REGISTRATION_PATCH.md` (import + ~9 handlers in `bot/main.py`,
button in `bot/keyboards/admin_menu.py`).

---

## 4. Web panel — `panel/...`

- Backend: add the two GW paths to `JSON_BODY_PATHS` in `panel/backend/proxy.py`
  (see `panel/backend/REGISTRATION_PATCH.py`).
- Frontend:
  - `src/api/gwApi.ts` — `gwApi` + `GwServer` interface.
  - `src/pages/ServersGw.tsx` — full CRUD table + editor modal.
  - Add a route in `App.tsx` and a nav item in `Layout.tsx` (see comments at top of
    `ServersGw.tsx`).

---

## 5. 5000+ concurrent connections — feasibility analysis

The question "can one SSH account hold 5000+ concurrent tunnels?" depends on which
limiting factor you hit first. With the installer's tuning:

| Limit | Default → tuned | Notes |
|---|---|---|
| File descriptors / `fs.file-max` | 1024 → **1048576** | Each SSH conn = ~2 fds (socket + channel). 5000 conn ≈ 10k fds — fine. |
| `fs.nr_open` | 1024 → **1048576** | Per-process fd ceiling. systemd unit also sets `LimitNOFILE=1048576`. |
| `nf_conntrack_max` | ~262144 → **1048576** | Each established conn = 1 conntrack entry. 5000 ≪ tuned. |
| `somaxconn` / `tcp_max_syn_backlog` | 128/1024 → **65535/65535** | Accept backlog; matters for bursty connect storms. |
| `ip_local_port_range` | 32768-60999 → **10000-65535** | Ephemeral ports for outbound (the node dials out via the tunnel). ~55k ports. |
| OpenSSH `MaxStartups` | 10:30:100 → **1000:30:5000** | Unauthenticated-startup throttling; the real constraint. |
| OpenSSH `MaxSessions` | 10 → **0** | 0 = no interactive sessions (forward-only, exactly what we want). |
| Memory | — | ~3-8 MB per OpenSSH connection (privsep + crypto). 5000 ≈ 15-40 GB **RAM** → this is the real ceiling. dropbear ≈ 1-3 MB/conn → 5000 ≈ 5-15 GB. |
| CPU | — | ChaCha20/AES-GCM + Curve25519 on connect; BBR helps throughput. A 4-core VPS saturates bandwidth before CPU at typical VPS NIC speeds. |
| Bandwidth | — | Usually the hard ceiling: a 1 Gbps NIC is ~125 MB/s; 5000 users avg 25 KB/s each = 125 MB/s — you're bandwidth-bound, not SSH-bound. |
| Cloudflare | — | Cloudflare WebSockets: no hard per-connection limit on standard plans, but **concurrent WS connections per zone** and **enterprise-only** features for very high sustained throughput. Free/Pro tiers are fine for thousands; beyond that, consider Workers/Pages WS or direct TLS (SNI mode, bypass CF) for some nodes. |

**Bottom line — don't promise 5000+ blindly:**
- On a **8 GB+ VPS with dropbear**, 5000 is achievable for light browsing traffic.
- With **OpenSSH privsep** the per-connection RAM cost roughly doubles; 5000 wants
  ~16 GB+ RAM. Use `--ssh-backend dropbear` for density.
- **Bandwidth, not SSH, is the usual ceiling.** Scale horizontally (more nodes) and
  rotate the shared account pool per node so one compromised client only leaks one
  node's creds.
- For >5000, add `MaxStartups 2000:30:10000`, raise `LimitNOFILE` and `nf_conntrack`
  further, and consider running multiple dropbear instances on different ports.

The installer's `gw-status` shows live session/conn counts and `file-max` so you can
watch the limits as you load-test.
