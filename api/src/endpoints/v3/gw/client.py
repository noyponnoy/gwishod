"""GW client API — encrypted config delivery to the Android client.

Endpoint: POST /vpn/api/v1/user/server_gw
Body (form, like the existing user/server* endpoints):
    { "user_id": "<app user id>", "pubkey": "<secp256k1 pubkey hex>", ...auth }

Returns, for each enabled GW server, an ECIES envelope (see crypto_gw.encrypt_config_to_user)
encrypting the full tunnel parameters. The public metadata (country/priority/etc.) is
returned in cleartext so the client can render the server list BEFORE decrypting — only
the secret tunnel params travel encrypted.

This endpoint sits under /vpn/api/v1/user/* so the existing AndroidSignatureMiddleware
(EXPECTED_SECRET) applies to it — the same auth the app already uses for user/server.
"""
from fastapi import APIRouter, Request, HTTPException

from src.db.v3.gw.server_pojo import ServerPojo
from src.utils.crypto_gw import encrypt_config_to_user, public_server_view

router = APIRouter()


def _field(body, *names, default=None):
    for n in names:
        if n in body and body[n] not in (None, ""):
            return body[n]
    return default


@router.post("/vpn/api/v1/user/server_gw")
async def client_get_servers_gw(request: Request):
    # accept both form-encoded (existing app convention) and json
    try:
        body = await request.json()
    except Exception:
        body = dict(await request.form())

    pubkey = _field(body, "pubkey", "public_key", "pub")
    if not pubkey:
        raise HTTPException(status_code=400, detail="pubkey is required")

    # quick sanity: secp256k1 pubkeys are 33 (compressed) or 65 (uncompressed) bytes hex
    try:
        b = bytes.fromhex(pubkey)
        if len(b) not in (33, 65):
            raise ValueError("bad length")
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid pubkey")

    servers = await ServerPojo.find_enabled()

    out = []
    for s in servers:
        # the secret blob the client decrypts and uses to build the tunnel
        secret = {
            "id": s.id,
            "ip_address": s.ip_address,
            "ssh_port": s.ssh_port,
            "ssh_username": s.ssh_username,
            "ssh_password": s.ssh_password,
            "proxy_host": s.proxy_host,
            "proxy_port": s.proxy_port,
            "proxy_scheme": s.proxy_scheme,
            "payload": s.payload,
            "sni": s.sni,
            "ssh_hostkey": s.ssh_hostkey,
        }
        try:
            envelope = encrypt_config_to_user(pubkey, secret)
        except Exception as e:
            # skip a server we can't encrypt to rather than fail the whole list
            continue
        out.append({
            "meta": public_server_view(s.to_doc()),
            "enc": envelope,
        })

    return {"ok": True, "servers": out, "count": len(out)}
