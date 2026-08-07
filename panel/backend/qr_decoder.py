"""Расшифровка QR-кода приложения (перенос bot/services/qr_decoder.py).

Приложение кодирует deviceId так:
  "<aes_ciphertext_hex>;<rsa_encrypted_aes_key_hex>"
Расшифровка: RSA-PKCS1v15 приватным ключом → AES-ключ → AES-ECB данных.

Делаем это на бекенде (а не в JS), потому что WebCrypto не поддерживает
AES-ECB и PKCS1v15 с закрытым ключом — перенос был бы ненадёжен.
"""
import logging

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_der_private_key

from .config import PRIVATE_RSA_KEY

logger = logging.getLogger(__name__)


def _decrypt_aes(data: str, priv_rsa_key: str, key_aes_encrypt: str) -> str | None:
    """Точная копия Crypto.decrypt_aes из бота."""
    try:
        priv_bytes = bytes.fromhex(priv_rsa_key)
        key_enc = bytes.fromhex(key_aes_encrypt)

        priv = load_der_private_key(priv_bytes, password=None, backend=default_backend())
        aes_key = priv.decrypt(key_enc, padding.PKCS1v15())

        cipher = Cipher(algorithms.AES(aes_key), modes.ECB(), backend=default_backend())
        dec = cipher.decryptor()
        data_bytes = bytes.fromhex(data)
        plain = dec.update(data_bytes) + dec.finalize()

        if plain:
            pad_len = plain[-1]
            if pad_len <= 16 and pad_len <= len(plain):
                plain = plain[:-pad_len]
        return plain.decode("utf-8")
    except Exception as e:
        logger.debug("QR AES decrypt failed: %s", e)
        return None


def decode_qr_text(raw: str) -> str | None:
    """Восстанавливает deviceId из QR-текста.

    Та же логика, что _resolve_qr в боте:
      • формат «data;key» → расшифровка, результат в верхнем регистре;
      • иначе возвращаем как есть (в верхнем регистре).
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    if ";" in raw:
        parts = raw.split(";")
        first = parts[0].strip()
        second = parts[1].strip() if len(parts) > 1 else ""
        if first and second:
            decrypted = _decrypt_aes(first, PRIVATE_RSA_KEY, second)
            if decrypted:
                return decrypted.upper()
    return raw.upper()
