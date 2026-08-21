#!/usr/bin/env bash
# =============================================================================
#  GW node uninstall / reset
# =============================================================================
#  Removes everything the GW installer created: services, config, the gw user,
#  firewall rules. Optionally keeps the gw user (e.g. to rotate password only).
#
#  Usage:   sudo bash uninstall.sh [options]
#    --keep-user       do not delete the gw system user / its home
#    --purge-logs      also remove /var/log/gw-node
#    -y, --yes         non-interactive
# =============================================================================
set -euo pipefail
KEEP_USER=0
PURGE_LOGS=0
INTERACTIVE=1
for a in "$@"; do
  case "$a" in
    --keep-user) KEEP_USER=1 ;;
    --purge-logs) PURGE_LOGS=1 ;;
    -y|--yes) INTERACTIVE=0 ;;
    -h|--help) sed -n '2,/^# =\{10,\}$/p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "unknown: $a" >&2 ;;
  esac
done
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 1; }

if [ "$INTERACTIVE" = 1 ]; then
  read -rp "Uninstall GW node? This stops services and removes config. [y/N] " ans
  [ "${ans:-}" = "y" ] || { echo "aborted"; exit 0; }
fi

echo "[gw] stopping services..."
systemctl disable --now gw-ws-bridge 2>/dev/null || true
systemctl disable --now gw-dropbear   2>/dev/null || true
rm -f /etc/systemd/system/gw-ws-bridge.service /etc/systemd/system/gw-dropbear.service
systemctl daemon-reload 2>/dev/null || true

echo "[gw] removing sshd drop-in (00-gw-node.conf)..."
rm -f /etc/ssh/sshd_config.d/00-gw-node.conf 2>/dev/null || true
systemctl restart ssh sshd 2>/dev/null || true

echo "[gw] removing firewall rules..."
rm -f /etc/nftables.d/30-gw-node.nft 2>/dev/null || true
systemctl reload nftables 2>/dev/null || nft -f /etc/nftables.conf 2>/dev/null || true

echo "[gw] removing sysctl tuning..."
rm -f /etc/sysctl.d/99-gw-node.conf
sysctl --system >/dev/null 2>&1 || true

echo "[gw] removing helper..."
rm -f /usr/local/bin/gw-status

if [ "$KEEP_USER" = 0 ]; then
  echo "[gw] deleting gw user..."
  id gw >/dev/null 2>&1 && (userdel -r gw 2>/dev/null || userdel gw 2>/dev/null || true)
fi

echo "[gw] removing config..."
rm -rf /etc/gw-node /var/lib/gw-node /run/gw-node
[ "$PURGE_LOGS" = 1 ] && rm -rf /var/log/gw-node

echo "[gw] done."
