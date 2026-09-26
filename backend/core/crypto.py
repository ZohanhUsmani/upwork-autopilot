import os
from cryptography.fernet import Fernet

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is None:
        key = os.getenv("ENCRYPTION_KEY", "")
        if not key:
            key = Fernet.generate_key().decode()
            import warnings
            warnings.warn(
                "ENCRYPTION_KEY env var not set — using ephemeral key. "
                "Set ENCRYPTION_KEY for persistence across restarts.",
                RuntimeWarning,
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
