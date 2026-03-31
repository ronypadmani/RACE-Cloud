"""
Security utilities for RACE-Cloud.
Handles password hashing and AWS credential encryption.
"""
import os
import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


# ── Password Hashing ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a password using bcrypt with auto-generated salt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its bcrypt hash."""
    return bcrypt.checkpw(
        password.encode('utf-8'),
        password_hash.encode('utf-8')
    )


# ── AWS Credential Encryption ─────────────────────────────────────────────────

def _get_fernet() -> Fernet:
    """Get Fernet instance using the configured encryption key."""
    key = current_app.config.get('FERNET_KEY', '')
    if not key:
        # Auto-generate and warn (development only)
        key = Fernet.generate_key().decode()
        current_app.config['FERNET_KEY'] = key
        current_app.logger.warning(
            "FERNET_ENCRYPTION_KEY not set! Auto-generated key for dev. "
            "Set FERNET_ENCRYPTION_KEY in .env for production."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_credential(plaintext: str) -> str:
    """Encrypt an AWS credential string using Fernet symmetric encryption."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode('utf-8')).decode('utf-8')


def decrypt_credential(ciphertext: str) -> str:
    """Decrypt an AWS credential string."""
    try:
        f = _get_fernet()
        return f.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        raise ValueError("Failed to decrypt credential. Encryption key may have changed.")


def mask_string(value: str, visible_chars: int = 4) -> str:
    """Mask a string, showing only the last N characters."""
    if len(value) <= visible_chars:
        return '*' * len(value)
    return '*' * (len(value) - visible_chars) + value[-visible_chars:]
