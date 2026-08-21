#!/usr/bin/env bash
# =============================================================================
#  GW node installer  —  SSH-over-CDN tunnel backend for GWVPN Android client
# =============================================================================
#  Installs and configures everything a GW VPS node needs:
#    * OpenSSH server tuned for high-concurrency TCP forwarding (dropbear optional)
#    * A locked-down "gw" system user that can ONLY do direct-tcpip port forwarding
#      (no shell, no PTY, no agent/X11 forwarding, no tunnel/SCP/SFTP)
#    * A WebSocket / HTTP 101 "Switching Protocols" bridge fronting the SSH port
#      so the Android client can ride a CDN (Cloudflare) in front of the node
#    * systemd units, firewall (nftables/ufw), kernel tuning for 5000+ conns
#
#  Usage:   sudo bash install.sh [options]
#    Options:
#      --ssh-port <port>        SSH listen port (default 22)
#      --ws-port <port>         WebSocket bridge HTTP port (default 80)
#      --wss-port <port>        WebSocket bridge HTTPS port (default 443, requires domain)
#      --domain <fqdn>          Domain for TLS (fronted by Cloudflare). Enables wss.
#      --ssh-backend <openssh|dropbear>   default openssh
#      --ws-backend <node|python>         default node (faster; python fallback if no node)
#      --gw-user <name>         restricted user name (default gw)
#      --gw-pass <password>     password for gw user (auto-generated if omitted)
#      --no-firewall            skip firewall configuration
#      --no-tuning              skip kernel sysctl tuning
#      -y, --yes                non-interactive (use defaults)
#      -h, --help
#
#  After install, read /etc/gw-node/credentials.txt for the generated gw password
#  and the WSocket bridge details to enter into the Telegram bot / API.
# =============================================================================
set -euo pipefail

# ---- defaults ---------------------------------------------------------------
GW_USER="gw"
SSH_PORT=22
WS_PORT=80
WSS_PORT=443
DOMAIN=""
SSH_BACKEND="openssh"
WS_BACKEND="node"
INTERACTIVE=1
DO_FIREWALL=1
DO_TUNING=1
GW_PASS=""

usage() { sed -n '2,/^# =\{10,\}$/p' "$0" | sed 's/^# \?//'; exit "${1:-0}"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --ssh-port)       SSH_PORT="$2"; shift 2 ;;
    --ws-port)        WS_PORT="$2"; shift 2 ;;
    --wss-port)       WSS_PORT="$2"; shift 2 ;;
    --domain)         DOMAIN="$2"; shift 2 ;;
    --ssh-backend)    SSH_BACKEND="$2"; shift 2 ;;
    --ws-backend)     WS_BACKEND="$2"; shift 2 ;;
    --gw-user)        GW_USER="$2"; shift 2 ;;
    --gw-pass)        GW_PASS="$2"; shift 2 ;;
    --no-firewall)    DO_FIREWALL=0; shift ;;
    --no-tuning)      DO_TUNING=0; shift ;;
    -y|--yes)         INTERACTIVE=0; shift ;;
    -h|--help)        usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage 1 ;;
  esac
done

need_root() {
  if [ "$(id -u)" -ne 0 ]; then
    echo "[!] Run as root (sudo)." >&2; exit 1
  fi
}
need_root

CONF_DIR="/etc/gw-node"
STATE_DIR="/var/lib/gw-node"
LOG_DIR="/var/log/gw-node"
RUN_DIR="/run/gw-node"
for d in "$CONF_DIR" "$STATE_DIR" "$LOG_DIR" "$RUN_DIR"; do
  mkdir -p "$d"; chmod 700 "$d"
done

log()  { echo -e "\033[1;32m[gw]\033[0m $*"; }
warn() { echo -e "\033[1;33m[gw!]\033[0m $*" >&2; }
die()  { echo -e "\033[1;31m[gw ERR]\033[0m $*" >&2; exit 1; }

detect_distro() {
  if [ -f /etc/debian_version ]; then echo "debian"
  elif [ -f /etc/redhat-release ]; then echo "rhel"
  elif [ -f /etc/alpine-release ]; then echo "alpine"
  else echo "unknown"; fi
}
DISTRO="$(detect_distro)"

# ---- package manager wrapper ------------------------------------------------
pkg_install() {
  case "$DISTRO" in
    debian) apt-get update -qq >/dev/null 2>&1; DEBIAN_FRONTEND=noninteractive apt-get install -y "$@" ;;
    rhel)   if command -v dnf >/dev/null; then dnf install -y "$@"; else yum install -y "$@"; fi ;;
    alpine) apk add --no-cache "$@" ;;
    *) die "Unsupported distro; install manually: $*" ;;
  esac
}

# ---- 1. base dependencies ----------------------------------------------------
log "Installing base dependencies..."
PACKAGES=(curl ca-certificates openssl)
case "$WS_BACKEND" in
  node)   PACKAGES+=(nodejs npm) ;;
  python) PACKAGES+=(python3 python3-pip) ;;
esac
if [ "$SSH_BACKEND" = "dropbear" ]; then PACKAGES+=(dropbear); else PACKAGES+=(openssh-server); fi
if [ "$DO_FIREWALL" = 1 ]; then PACKAGES+=(nftables); fi
pkg_install "${PACKAGES[@]}"

# ---- 2. kernel tuning for high concurrency ----------------------------------
if [ "$DO_TUNING" = 1 ]; then
  log "Applying kernel sysctl tuning for 5000+ concurrent connections..."
  cat > /etc/sysctl.d/99-gw-node.conf <<EOF
# --- GW node high-concurrency tuning ---
# file descriptors
fs.file-max = 1048576
fs.nr_open = 1048576

# connection tracking
net.netfilter.nf_conntrack_max = 1048576
net.netfilter.nf_conntrack_tcp_timeout_established = 7200
net.netfilter.nf_conntrack_buckets = 262144

# TCP backlog & buffers
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 10000 65535
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216

# keep SSH connections alive through idle ISPs
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 15
net.ipv4.tcp_keepalive_probes = 6

# enable BBR congestion control if available
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
EOF
  sysctl --system >/dev/null 2>&1 || warn "some sysctl keys need newer kernel/modules (ignored)"
  # limits.conf for the gw user & services
  if ! grep -q "gw-node" /etc/security/limits.conf 2>/dev/null; then
    cat >> /etc/security/limits.conf <<EOF
# gw-node
*               soft    nofile          1048576
*               hard    nofile          1048576
root            soft    nproc           65535
root            hard    nproc           65535
EOF
  fi
fi

# ---- 3. restricted gw system user -------------------------------------------
ensure_gw_user() {
  if id "$GW_USER" >/dev/null 2>&1; then
    log "User '$GW_USER' already exists."
  else
    log "Creating locked-down user '$GW_USER'..."
    # nologin shell: no interactive session possible. We also ForceCommand /bin/false
    # in sshd_config for belt-and-suspenders (forwarding still works without a session).
    if [ "$DISTRO" = "alpine" ]; then
      adduser -D -s /usr/sbin/nologin -h "$STATE_DIR/home" "$GW_USER" 2>/dev/null || true
    else
      useradd --system --shell /usr/sbin/nologin --home-dir "$STATE_DIR/home" "$GW_USER"
    fi
    mkdir -p "$STATE_DIR/home"; chown "$GW_USER":"$GW_USER" "$STATE_DIR/home"
  fi
}
ensure_gw_user

# generate password if not provided
if [ -z "$GW_PASS" ]; then
  # 18-char base62 password, no shell metacharacters
  GW_PASS="$(head -c 24 /dev/urandom | base64 | tr -d '/+=' | cut -c1-18)"
fi
# set password (used only by password-auth SSH; forward-only user)
if [ "$DISTRO" = "alpine" ]; then echo "$GW_USER:$GW_PASS" | chpasswd; else echo "$GW_USER:$GW_PASS" | chpasswd; fi

# ---- 4. SSH server configuration --------------------------------------------
SSH_HOST_KEY_ED25519="/etc/ssh/ssh_host_ed25519_key"
if [ "$SSH_BACKEND" = "openssh" ]; then
  log "Configuring OpenSSH server (port $SSH_PORT, forwarding-only for $GW_USER)..."
  # ensure host keys exist
  ssh-keygen -A >/dev/null 2>&1 || true

  SSHD_CONF_DIR="/etc/ssh/sshd_config.d"
  mkdir -p "$SSHD_CONF_DIR"
  cat > "$SSHD_CONF_DIR/00-gw-node.conf" <<EOF
# --- GW node OpenSSH tuning ---
Port $SSH_PORT
AddressFamily any
ListenAddress 0.0.0.0
ListenAddress ::

# ---- high concurrency ----
MaxStartups 1000:30:5000
MaxSessions 0
LoginGraceTime 20
MaxAuthTries 3

# ---- keep idle tunnels alive through NAT ----
ClientAliveInterval 30
ClientAliveCountMax 720

# ---- crypto: fast modern curves only ----
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com
MACs umac-128-etm@openssh.com,hmac-sha2-256-etm@openssh.com
HostKeyAlgorithms ssh-ed25519,ssh-ed25519-cert-v01@openssh.com

# ---- allow password auth (the gw account is forward-only & has no shell) ----
PasswordAuthentication yes
PermitRootLogin no
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys

# ---- hardening ----
PermitTTY no
X11Forwarding no
AllowAgentForwarding no
AllowTcpForwarding yes
PermitTunnel no
AllowStreamLocalForwarding no
GatewayPorts no
PrintMotd no
AcceptEnv LANG LC_*
UseDNS no
GSSAPIAuthentication no
UsePAM yes

# ---- Match block: lock the gw user to forward-only ----
Match User $GW_USER
    ForceCommand /bin/false
    PermitTTY no
    X11Forwarding no
    AllowAgentForwarding no
    AllowTcpForwarding yes
    PermitTunnel no
    AllowStreamLocalForwarding no
    PermitOpen any
    PermitListen none
EOF

  # restart sshd
  if command -v systemctl >/dev/null 2>&1; then
    systemctl enable ssh >/dev/null 2>&1 || systemctl enable sshd >/dev/null 2>&1 || true
    systemctl restart ssh 2>/dev/null || systemctl restart sshd
  else
    # alpine: openrc
    rc-update add sshd default 2>/dev/null || true
    rc-service sshd restart 2>/dev/null || /usr/sbin/sshd
  fi
else
  log "Configuring dropbear (port $SSH_PORT) — lighter for very high concurrency..."
  # dropbear: -F foreground, -p port, -s disable password logins for root,
  # we WANT password login for gw. -K keepalive 30.
  DB_KEY="$CONF_DIR/dropbear_ed25519_key"
  [ -f "$DB_KEY" ] || dropbearkey -t ed25519 -f "$DB_KEY" >/dev/null 2>&1 || true
  cat > /etc/systemd/system/gw-dropbear.service <<EOF
[Unit]
Description=GW dropbear SSH (forward-only)
After=network.target

[Service]
Type=simple
ExecStart=/usr/sbin/dropbear -F -E -R -K 30 -p $SSH_PORT -P /run/gw-dropbear.pid
Restart=on-failure
RestartSec=3
LimitNOFILE=1048576
# dropbear has no per-user ForceCommand; rely on nologin shell + iptables not needed
# (the gw user shell is /usr/sbin/nologin; direct-tcpip forwarding works without a session)

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now gw-dropbear
fi

# ---- 5. WebSocket / HTTP-101 "Switching Protocols" bridge -------------------
# This is what the Android client's payload (GET / HTTP/1.1\r\n...Upgrade: websocket)
# actually talks to when fronting the node through Cloudflare. It accepts an HTTP
# upgrade, replies 101 Switching Protocols, then bridges raw bytes to the local SSH port.
# When Cloudflare is in front, Cloudflare performs the real WebSocket upgrade on the edge
# and tunnels the upgraded stream to this backend on port 80/443.

write_ws_bridge_node() {
  cat > "$CONF_DIR/ws-bridge.js" <<'JSEOF'
/* GW WebSocket / HTTP-101 bridge.
 * Accepts an HTTP "Upgrade: websocket" request, replies with
 *   HTTP/1.1 101 Switching Protocols\r\nContent-Length: <huge>\r\n\r\n
 * then bridges raw bytes to the local SSH port.
 * Mirrors the PANCHO7532 WS-Proxy approach but hardens it:
 *   - per-connection fd/hard limits, backpressure-safe piping,
 *   - idle timeout, error handling, no crash on bad clients.
 */
const net = require("net");
const fs = require("fs");

const CONF = "/etc/gw-node/ws-bridge.env";
const env = fs.existsSync(CONF) ? Object.fromEntries(
  fs.readFileSync(CONF, "utf8").split("\n")
    .filter(l => l && !l.startsWith("#") && l.includes("="))
    .map(l => { const i = l.indexOf("="); return [l.slice(0,i).trim(), l.slice(i+1).trim()]; })
) : {};

const BACKEND_HOST = env.BACKEND_HOST || "127.0.0.1";
const BACKEND_PORT = parseInt(env.BACKEND_PORT || "22", 10);
const LISTEN_HTTP  = parseInt(env.LISTEN_HTTP  || "80", 10);
const LISTEN_HTTPS = parseInt(env.LISTEN_HTTPS || "443", 10);
const TLS_CERT     = env.TLS_CERT || "";
const TLS_KEY      = env.TLS_KEY  || "";
const MAX_CONN     = parseInt(env.MAX_CONN || "8000", 10);
const IDLE_MS      = parseInt(env.IDLE_MS  || "900000", 10); // 15 min
const CONTENT_LEN  = "1048576000000";

let active = 0;

function bridge(socket) {
  if (active >= MAX_CONN) { socket.end("HTTP/1.1 503 Service Unavailable\r\n\r\n"); return; }
  active++;
  let upgraded = false;
  let backend = null;
  const idle = setTimeout(() => socket.destroy(), IDLE_MS);
  const reset = () => { clearTimeout(idle); socket.removeAllListeners(); if (backend) backend.destroy(); if (!upgraded) {} active = Math.max(0, active - 1); };

  // Send the 101 response immediately (the client payload already convinced the CDN
  // to upgrade; here we confirm and switch to raw byte tunneling).
  try {
    socket.write("HTTP/1.1 101 Switching Protocols\r\nContent-Length: " + CONTENT_LEN + "\r\n\r\n");
  } catch (e) { reset(); return; }
  upgraded = true;

  backend = net.createConnection({ host: BACKEND_HOST, port: BACKEND_PORT });
  backend.on("connect", () => {
    // backpressure-safe pipe both ways
    socket.on("data", d => { const ok = backend.write(d); if (!ok) socket.pause(); });
    backend.on("drain", () => socket.resume());
    backend.on("data", d => { const ok = socket.write(d); if (!ok) backend.pause(); });
    socket.on("drain", () => backend.resume());
  });
  const teardown = () => reset();
  socket.on("error", teardown);
  socket.on("close", teardown);
  socket.on("end",   teardown);
  backend.on("error", teardown);
  backend.on("close", teardown);
  backend.on("end",   teardown);
}

function startHttp() {
  const srv = net.createServer(bridge);
  srv.on("error", e => console.error("[http] " + e));
  srv.listen(LISTEN_HTTP, () => console.log(`[gw] WS bridge (HTTP)  on :${LISTEN_HTTP} -> ${BACKEND_HOST}:${BACKEND_PORT}`));
}

function startHttps() {
  if (!TLS_CERT || !TLS_KEY || !require("fs").existsSync(TLS_CERT)) {
    console.warn("[gw] wss requested but no TLS cert; skipping HTTPS listener.");
    return;
  }
  const tls = require("tls");
  const opts = { cert: fs.readFileSync(TLS_CERT), key: fs.readFileSync(TLS_KEY) };
  const srv = tls.createServer(opts, bridge);
  srv.on("error", e => console.error("[https] " + e));
  srv.listen(LISTEN_HTTPS, () => console.log(`[gw] WS bridge (HTTPS) on :${LISTEN_HTTPS} -> ${BACKEND_HOST}:${BACKEND_PORT}`));
}

startHttp();
startHttps();

// graceful
process.on("SIGTERM", () => process.exit(0));
process.on("SIGINT",  () => process.exit(0));
JSEOF
}

write_ws_bridge_python() {
  cat > "$CONF_DIR/ws-bridge.py" <<'PYEOF'
#!/usr/bin/env python3
"""GW WebSocket / HTTP-101 bridge (pure-stdlib fallback when node is unavailable).
Replies 101 Switching Protocols and bridges raw bytes to the local SSH port.
"""
import os, socket, threading, ssl, sys

CONF = "/etc/gw-node/ws-bridge.env"
env = {}
if os.path.exists(CONF):
    for line in open(CONF):
        line=line.strip()
        if line and not line.startswith("#") and "=" in line:
            k,v=line.split("=",1); env[k.strip()]=v.strip()

BACKEND_HOST = env.get("BACKEND_HOST","127.0.0.1")
BACKEND_PORT = int(env.get("BACKEND_PORT","22"))
LISTEN_HTTP  = int(env.get("LISTEN_HTTP","80"))
LISTEN_HTTPS = int(env.get("LISTEN_HTTPS","443"))
TLS_CERT = env.get("TLS_CERT","")
TLS_KEY  = env.get("TLS_KEY","")
MAX_CONN = int(env.get("MAX_CONN","8000"))
IDLE     = float(env.get("IDLE_MS","900000"))/1000.0
CONTENT_LEN = b"1048576000000"
active = 0
lock = threading.Lock()

def pipe(a, b):
    try:
        while True:
            data = a.recv(65536)
            if not data: break
            b.sendall(data)
    except Exception:
        pass
    finally:
        try: b.shutdown(socket.SHUT_WR)
        except Exception: pass

def bridge(conn, addr):
    global active
    with lock:
        if active >= MAX_CONN:
            conn.sendall(b"HTTP/1.1 503 Service Unavailable\r\n\r\n"); conn.close(); return
        active += 1
    try:
        conn.settimeout(IDLE)
        conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nContent-Length: " + CONTENT_LEN + b"\r\n\r\n")
        conn.settimeout(None)
        backend = socket.create_connection((BACKEND_HOST, BACKEND_PORT), timeout=10)
        conn.settimeout(IDLE); backend.settimeout(IDLE)
        t1 = threading.Thread(target=pipe, args=(conn, backend), daemon=True)
        t2 = threading.Thread(target=pipe, args=(backend, conn), daemon=True)
        t1.start(); t2.start(); t1.join(); t2.join()
        backend.close()
    except Exception as e:
        sys.stderr.write(f"[gw] {addr}: {e}\n")
    finally:
        try: conn.close()
        except Exception: pass
        with lock: active = max(0, active-1)

def serve(host, port, tls_ctx=None):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port)); s.listen(1024)
    print(f"[gw] WS bridge ({'HTTPS' if tls_ctx else 'HTTP'}) on :{port} -> {BACKEND_HOST}:{BACKEND_PORT}", flush=True)
    while True:
        c, a = s.accept()
        if tls_ctx:
            try: c = tls_ctx.wrap_socket(c, server_side=True)
            except Exception: c.close(); continue
        threading.Thread(target=bridge, args=(c,a), daemon=True).start()

def main():
    th = threading.Thread(target=serve, args=("0.0.0.0", LISTEN_HTTP), daemon=True); th.start()
    if TLS_CERT and os.path.exists(TLS_CERT) and os.path.exists(TLS_KEY):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(TLS_CERT, TLS_KEY)
        threading.Thread(target=serve, args=("0.0.0.0", LISTEN_HTTPS, ctx), daemon=True).start()
    while True: threading.Event().wait(3600)

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: pass
PYEOF
  chmod +x "$CONF_DIR/ws-bridge.py"
}

log "Writing WebSocket bridge ($WS_BACKEND backend)..."
# ws-bridge.env (read by both node & python variants)
TLS_CERT_PATH=""; TLS_KEY_PATH=""
if [ -n "$DOMAIN" ]; then
  # Generate a self-signed cert; Cloudflare "Full" mode accepts it on the origin.
  # For strict mode the operator should replace with a real cert / CF origin cert.
  TLS_CERT_PATH="$CONF_DIR/gw-bridge.crt"
  TLS_KEY_PATH="$CONF_DIR/gw-bridge.key"
  if [ ! -f "$TLS_CERT_PATH" ]; then
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
      -keyout "$TLS_KEY_PATH" -out "$TLS_CERT_PATH" \
      -subj "/CN=$DOMAIN" >/dev/null 2>&1 || true
    chmod 600 "$TLS_KEY_PATH"
  fi
fi
cat > "$CONF_DIR/ws-bridge.env" <<EOF
# GW WebSocket bridge configuration (read by ws-bridge.js / ws-bridge.py)
BACKEND_HOST=127.0.0.1
BACKEND_PORT=$SSH_PORT
LISTEN_HTTP=$WS_PORT
LISTEN_HTTPS=$WSS_PORT
TLS_CERT=$TLS_CERT_PATH
TLS_KEY=$TLS_KEY_PATH
MAX_CONN=8000
IDLE_MS=900000
EOF

if [ "$WS_BACKEND" = "node" ] && command -v node >/dev/null 2>&1; then
  write_ws_bridge_node
  BRIDGE_EXEC="node $CONF_DIR/ws-bridge.js"
else
  WS_BACKEND="python"
  write_ws_bridge_python
  BRIDGE_EXEC="/usr/bin/env python3 $CONF_DIR/ws-bridge.py"
fi

# systemd unit for the bridge
cat > /etc/systemd/system/gw-ws-bridge.service <<EOF
[Unit]
Description=GW WebSocket / HTTP-101 bridge to local SSH
After=network.target

[Service]
Type=simple
ExecStart=$BRIDGE_EXEC
Restart=on-failure
RestartSec=3
LimitNOFILE=1048576
StandardOutput=append:$LOG_DIR/ws-bridge.log
StandardError=append:$LOG_DIR/ws-bridge.log

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now gw-ws-bridge

# ---- 6. firewall -------------------------------------------------------------
if [ "$DO_FIREWALL" = 1 ]; then
  log "Configuring nftables firewall..."
  # Allow SSH (admin), the WS bridge ports, and established traffic; drop the rest IN.
  # NOTE: we keep the admin SSH port open so you don't lock yourself out. If your admin
  # ssh port differs from GW_SSH_PORT, adjust GW_SSH_PORT below or use --ssh-port.
  cat > /etc/nftables.d/30-gw-node.nft <<NFT
table inet gw-node-filter {
  set gw_v4 { type ipv4_addr; flags interval; elements = { 0.0.0.0/0 } }
  chain input {
    type filter hook input priority 0; policy accept;
    # established/related
    ct state established,related accept
    # loopback
    iif "lo" accept
    # ICMP (ping) — rate limited
    ip protocol icmp limit rate 5/second accept
    ip6 nexthdr icmpv6 accept
    # admin SSH (do NOT lock yourself out)
    tcp dport $SSH_PORT accept
    # WS bridge
    tcp dport $WS_PORT accept
    tcp dport $WSS_PORT accept
    # drop everything else inbound (the node is egress-only for tunneled traffic)
    drop
  }
  chain forward { type filter hook forward priority 0; policy accept; }
  chain output  { type filter hook output  priority 0; policy accept; }
}
NFT
  mkdir -p /etc/nftables.d
  # include the drop-in if nftables main conf supports it
  if [ -f /etc/nftables.conf ] && ! grep -q "include.*nftables.d" /etc/nftables.conf; then
    printf '\ninclude "/etc/nftables.d/*.nft"\n' >> /etc/nftables.conf
  fi
  systemctl enable nftables 2>/dev/null || true
  systemctl restart nftables 2>/dev/null || nft -f /etc/nftables.conf || warn "nftables reload skipped"
fi

# ---- 7. status helper -------------------------------------------------------
cat > /usr/local/bin/gw-status <<'STAT'
#!/usr/bin/env bash
echo "===== GW node status ====="
echo "-- services --"
systemctl is-active gw-ws-bridge 2>/dev/null | sed 's/^/gw-ws-bridge: /'
if systemctl is-active gw-dropbear >/dev/null 2>&1; then
  systemctl is-active gw-dropbear | sed 's/^/gw-dropbear: /'
else
  systemctl is-active ssh sshd 2>/dev/null | sed 's/^/ssh: /'
fi
echo "-- gw user --"
id gw 2>/dev/null || echo "gw: missing"
echo "-- listening ports --"
ss -ltnp 2>/dev/null | grep -E ':(22|80|443)\b' || true
echo "-- active SSH forwarding sessions (approx) --"
ss -tn state established '( dport = :22 or sport = :22 )' 2>/dev/null | wc -l
echo "-- ws bridge connections --"
ss -tn state established '( sport = :80 or sport = :443 )' 2>/dev/null | wc -l
echo "-- resource limits --"
cat /proc/sys/fs/file-max | sed 's/^/file-max: /'
echo "-- credentials location --"
[ -f /etc/gw-node/credentials.txt ] && echo "/etc/gw-node/credentials.txt" || echo "none"
STAT
chmod +x /usr/local/bin/gw-status

# ---- 8. save credentials / summary ------------------------------------------
PUBKEY=""
[ -f "$SSH_HOST_KEY_ED25519.pub" ] && PUBKEY="$(cat $SSH_HOST_KEY_ED25519.pub)"
cat > "$CONF_DIR/credentials.txt" <<EOF
# GW node credentials — generated $(date -u +%FT%TZ)
# KEEP THIS FILE PRIVATE. chmod 600.

gw_user        = $GW_USER
gw_password    = $GW_PASS
ssh_host       = $(hostname -I 2>/dev/null | awk '{print $1}')
ssh_port       = $SSH_PORT
ws_bridge_http = $WS_PORT
ws_bridge_https= $WSS_PORT
domain         = ${DOMAIN:-<none>}
ssh_backend    = $SSH_BACKEND
ws_backend     = $WS_BACKEND
ssh_hostkey_ed25519_pub = $PUBKEY

# Enter these into the Telegram bot / API "GW" server section:
#   proxy_host = <domain or node IP>   (the CDN-fronted host the client connects to)
#   proxy_port = $WS_PORT  (or $WSS_PORT if behind Cloudflare HTTPS)
#   ssh_host   = <node IP or domain>
#   ssh_port   = $SSH_PORT
#   ssh_username = $GW_USER
#   ssh_password = $GW_PASS
#   payload    = GET / HTTP/1.1[crlf]Host: <domain>[crlf]Connection: Upgrade[crlf]User-Agent: [ua][crlf]Upgrade: websocket[crlf][crlf]
EOF
chmod 600 "$CONF_DIR/credentials.txt"

log "============================================================"
log " GW node installed successfully."
log " Run 'gw-status' to check service health."
log " Credentials: $CONF_DIR/credentials.txt  (chmod 600)"
log "============================================================"
if [ "$INTERACTIVE" = 1 ]; then
  warn "Review /etc/gw-node/credentials.txt and enter it into the bot/API."
fi
