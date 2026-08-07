from mnemonic import Mnemonic
from hdwallet import HDWallet
from hdwallet.symbols import ETH
import hashlib


async def generate_mnemonic() -> str:
    """Generate a BIP-39 mnemonic phrase (24 words from 256-bit entropy)."""
    m = Mnemonic("english")
    words = m.generate(strength=256)
    return words


async def mnemonic_to_xprv(mnemonic_phrase: str) -> str:
    """
    Convert mnemonic to extended private key and return the public key (user_id).
    Uses derivation path m/44'/60'/0'/0/0 (Ethereum standard).
    Returns the public key as the user identifier.
    """
    hd_wallet = HDWallet(symbol=ETH)
    hd_wallet.from_mnemonic(mnemonic=mnemonic_phrase)
    hd_wallet.from_path("m/44'/60'/0'/0/0")
    return hd_wallet.public_key()


def mnemonic_to_device_id(mnemonic_phrase: str) -> str | None:
    try:
        m = Mnemonic("english")
        if not m.check(mnemonic_phrase):
            return None

        # Step 1: mnemonic -> entropy (BIP-39)
        entropy = m.to_entropy(mnemonic_phrase)

        # Step 2: entropy as seed -> HMAC-SHA512("Bitcoin seed", entropy)
        master = hmac.new(b"Bitcoin seed", bytes(entropy), hashlib.sha512).digest()
        secret_key = master[:32]

        # Step 3: secret key -> public key (secp256k1, 64 bytes x+y, no 04 prefix)
        from ecdsa import SECP256k1, SigningKey
        sk = SigningKey.from_string(secret_key, curve=SECP256k1)
        vk = sk.get_verifying_key()
        public_key_bytes = vk.to_string()  # 64 bytes (x+y)

        # Step 4: hex uppercase (like HexUtils.toString)
        device_id = public_key_bytes.hex().upper()
        return device_id
    except Exception:
        return None
