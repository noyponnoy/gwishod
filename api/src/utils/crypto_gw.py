"""Encrypted GW config delivery — ECIES envelope (secp256k1 ECDH + AES-256-GCM).

Why this design (and the honest limitation):
  The Android client must receive SSH credentials (user/pass), proxy host/port,
  payload and SNI to build the tunnel. Sending them in plaintext lets a passive
  observer harvest the entire server fleet's creds from one API response.

  We encrypt the per-server config to the *individual user's* secp256k1 public key
  (the same BIP-39 / Ethereum-derived key the app already uses for user identity —
  see api/src/utils/crypto_user.py). The envelope is ECIES:

      ephemeral_secp256k1_keypair  --ECDH-->  shared_secret
      shared_secret --SHA256-->  AES-256 key + IV
      plaintext_config  --AES-256-GCM-->  ciphertext + 16-byte tag
      envelope = { "eph" : ephemeral_pubkey (hex),
                   "ct"  : base64(ciphertext || tag),
                   "iv"  : base64(iv) }

  The client decrypts with its own secp256k1 private key (held in Android Keystore
  where the device supports it). No symmetric key is baked into the APK. A single
  compromised client reveals only the configs it personally received — not a global
  key, not other users' configs.

  Honest limitation: a client that can decrypt a config can also *exfiltrate* that
  config. This scheme prevents mass harvesting by network observers and by APK
  extraction of a shared key, but it cannot prevent a sufficiently determined
  attacker who fully compromises one client AND targets the specific configs that
  client received. We mitigate blast radius further with credential rotation and a
  small pool of shared SSH accounts (see README-GW.md), never a single global secret.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from typing import Any, Dict, Optional

try:
    # coincurve is the fastest, most reliable secp256k1 lib in Python.
    # Falls back to a pure-python implementation if unavailable.
    from coincurve import PrivateKey as _CCPriv, PublicKey as _CCPub  # type: ignore

    _HAVE_COINCURVE = True
except Exception:  # pragma: no cover - fallback path
    _HAVE_COINCURVE = False

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    _HAVE_CRYPTOGRAPHY = True
except Exception:  # pragma: no cover
    _HAVE_CRYPTOGRAPHY = False


# ----------------------------------------------------------------------------
# secp256k1 primitives
# ----------------------------------------------------------------------------
def _ecdh_shared_secret(priv_hex: str, pub_hex: str) -> bytes:
    """Compute the X coordinate of the ECDH shared secret (32 bytes)."""
    if _HAVE_COINCURVE:
        priv = _CCPriv(bytes.fromhex(priv_hex))
        pub = _CCPub(bytes.fromhex(pub_hex))
        return priv.ecdh(pub.format())  # returns sha256(compressed ss) by default
    # pure-python fallback using ecdsa lib if present
    try:
        from ecdsa import ECDH, SigningKey, VerifyingKey, SECP256k1  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Need coincurve or ecdsa for secp256k1 ECDH. pip install coincurve"
        ) from exc
    sk = SigningKey.from_string(bytes.fromhex(priv_hex), curve=SECP256k1)
    vk = VerifyingKey.from_string(bytes.fromhex(pub_hex), curve=SECP256k1)
    ecdh = ECDH(curve=SECP256k1)
    ecdh.load_private_key(sk)
    ecdh.load_received_public_key(vk)
    shared = ecdh.generate_shared_secret_bytes()
    return hashlib.sha256(shared).digest()


def _derive_key_iv(shared: bytes) -> tuple[bytes, bytes]:
    """HKDF-ish single-step derivation of a 32-byte AES key + 12-byte GCM IV."""
    # SHA256(shared || 'gw|key') for key, SHA256(shared || 'gw|iv')[:12] for iv
    key = hashlib.sha256(shared + b"gw|key").digest()
    iv = hashlib.sha256(shared + b"gw|iv").digest()[:12]
    return key, iv


# ----------------------------------------------------------------------------
# server-side encrypt
# ----------------------------------------------------------------------------
def encrypt_config_to_user(pub_hex: str, plaintext: Dict[str, Any]) -> Dict[str, str]:
    """Encrypt a config dict to the user's secp256k1 public key (hex, 33/65 bytes).

    Returns the JSON-serializable envelope:
      { "eph": "<ephemeral pubkey hex>", "ct": "<base64>", "iv": "<base64>" }
    """
    if not _HAVE_COINCURVE:
        raise RuntimeError("encrypt_config_to_user requires coincurve on the server.")
    if not _HAVE_CRYPTOGRAPHY:
        raise RuntimeError("encrypt_config_to_user requires the cryptography package.")

    # 1. ephemeral keypair
    eph_priv = _CCPriv(secrets.token_bytes(32))
    eph_pub_bytes = eph_priv.public_key.format()  # compressed (33 bytes)
    eph_pub_hex = eph_pub_bytes.hex()

    # 2. ECDH with the user's pubkey
    user_pub = _CCPub(bytes.fromhex(pub_hex))
    shared = eph_priv.ecdh(user_pub.format())

    # 3. derive AES-256-GCM key + IV
    key, iv = _derive_key_iv(shared)

    # 4. encrypt
    aes = AESGCM(key)
    pt = json.dumps(plaintext, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ct_and_tag = aes.encrypt(iv, pt, associated_data=b"gw-config-v1")
    return {
        "eph": eph_pub_hex,
        "ct": base64.b64encode(ct_and_tag).decode("ascii"),
        "iv": base64.b64encode(iv).decode("ascii"),
    }


# ----------------------------------------------------------------------------
# client-side decrypt (mirrored in Kotlin on Android; kept here for tests/panel)
# ----------------------------------------------------------------------------
def decrypt_config_with_priv(priv_hex: str, envelope: Dict[str, str]) -> Dict[str, Any]:
    """Decrypt an envelope with the user's secp256k1 private key (hex)."""
    if not _HAVE_CRYPTOGRAPHY:
        raise RuntimeError("decrypt_config_with_priv requires the cryptography package.")
    eph_pub_hex = envelope["eph"]
    shared = _ecdh_shared_secret(priv_hex, eph_pub_hex)
    key, iv = _derive_key_iv(shared)
    aes = AESGCM(key)
    ct_and_tag = base64.b64decode(envelope["ct"])
    iv_bytes = base64.b64decode(envelope["iv"])
    pt = aes.decrypt(iv_bytes, ct_and_tag, associated_data=b"gw-config-v1")
    return json.loads(pt.decode("utf-8"))


# ----------------------------------------------------------------------------
# helper: the public-facing (safe) projection of a server — NO secrets
# ----------------------------------------------------------------------------
def public_server_view(server: Dict[str, Any]) -> Dict[str, Any]:
    """What the API can return without encryption: metadata + status only."""
    return {
        "id": server.get("id"),
        "name": server.get("name"),
        "country": server.get("country"),
        "country_code": server.get("country_code"),
        "state": server.get("state"),
        "premium": server.get("premium", False),
        "recommend": server.get("recommend", False),
        "priority": server.get("priority", 0),
        "status": server.get("status", True),
        # NOTE: ssh creds / proxy / payload / sni are NOT included here.
    }
