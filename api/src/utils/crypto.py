from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_der_private_key
from cryptography.hazmat.backends import default_backend


class Crypto:
    @staticmethod
    def decrypt_aes(data: str, priv_rsa_key: str, key_aes_encrypt: str) -> str | None:
        """
        Decrypt AES-256-ECB encrypted data.
        - data: hex-encoded encrypted data
        - priv_rsa_key: hex-encoded PKCS8 DER RSA private key
        - key_aes_encrypt: hex-encoded RSA-encrypted AES key
        """
        try:
            priv_rsa_key_bytes = bytes.fromhex(priv_rsa_key)
            key_aes_encrypt_bytes = bytes.fromhex(key_aes_encrypt)

            # Decrypt the AES key using RSA PKCS1v15
            rsa_private_key = load_der_private_key(priv_rsa_key_bytes, password=None, backend=default_backend())
            decrypted_key = rsa_private_key.decrypt(key_aes_encrypt_bytes, padding.PKCS1v15())

            # Create AES-256-ECB cipher (block-by-block decryption matches Rust Aes256::decrypt_block)
            cipher = Cipher(algorithms.AES(decrypted_key), modes.ECB(), backend=default_backend())
            decryptor = cipher.decryptor()

            data_bytes = bytes.fromhex(data)
            decrypted_data = decryptor.update(data_bytes) + decryptor.finalize()

            # Remove PKCS7 padding
            if decrypted_data:
                padding_len = decrypted_data[-1]
                if padding_len <= 16 and padding_len <= len(decrypted_data):
                    decrypted_data = decrypted_data[:-padding_len]

            return decrypted_data.decode("utf-8")
        except Exception:
            return None

    @staticmethod
    def decrypt_rsa(priv_rsa_key: str, encrypted_aes: str) -> str | None:
        """
        Decrypt RSA-encrypted data using PKCS1v15 padding.
        Returns hex-encoded decrypted data.
        """
        try:
            priv_rsa_key_bytes = bytes.fromhex(priv_rsa_key)
            encrypted_aes_bytes = bytes.fromhex(encrypted_aes)

            rsa_private_key = load_der_private_key(priv_rsa_key_bytes, password=None, backend=default_backend())
            decrypted_key = rsa_private_key.decrypt(encrypted_aes_bytes, padding.PKCS1v15())

            return decrypted_key.hex()
        except Exception:
            return None
