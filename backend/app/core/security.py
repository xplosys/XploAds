"""Security primitives: password hashing, JWTs, opaque tokens, secret encryption, TOTP."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

# Argon2id with OWASP-recommended parameters (m=19 MiB, t=2, p=1).
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
# Pre-computed hash used to equalize timing when the account does not exist.
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# --- Opaque tokens -----------------------------------------------------------------------------------------


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Tokens are high-entropy, so a fast keyed hash is appropriate (and allows indexed lookup)."""
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# --- JWT access tokens -------------------------------------------------------------------------------------


def create_access_token(*, user_id: uuid.UUID, session_id: uuid.UUID) -> tuple[str, int]:
    s = get_settings()
    now = datetime.now(UTC)
    ttl = s.access_token_ttl_seconds
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "iss": s.jwt_issuer,
        "aud": s.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=ttl),
        "jti": uuid.uuid4().hex,
        "typ": "access",
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256"), ttl


def decode_access_token(token: str) -> dict[str, Any]:
    s = get_settings()
    payload = jwt.decode(
        token,
        s.jwt_secret,
        algorithms=["HS256"],
        audience=s.jwt_audience,
        issuer=s.jwt_issuer,
        options={"require": ["exp", "sub", "sid", "iss", "aud"]},
    )
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload


# --- Secret encryption (envelope) --------------------------------------------------------------------------


def _kek() -> bytes:
    raw = get_settings().data_encryption_key
    key = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    if len(key) != 32:
        raise RuntimeError("DATA_ENCRYPTION_KEY must decode to 32 bytes")
    return key


def encrypt_secret(plaintext: str, *, associated_data: bytes = b"") -> bytes:
    """Envelope encryption: a random data key encrypts the secret; the KEK encrypts the data key.

    Layout: version(1) | wrapped_dek_nonce(12) | wrapped_dek(48) | nonce(12) | ciphertext.
    The KEK lives outside the database (env / secret manager), so a database dump alone cannot decrypt secrets.
    """
    dek = AESGCM.generate_key(bit_length=256)
    n1, n2 = os.urandom(12), os.urandom(12)
    wrapped = AESGCM(_kek()).encrypt(n1, dek, b"xploads-dek")
    ct = AESGCM(dek).encrypt(n2, plaintext.encode(), associated_data)
    return b"\x01" + n1 + wrapped + n2 + ct


def decrypt_secret(blob: bytes, *, associated_data: bytes = b"") -> str:
    if not blob or blob[0] != 1:
        raise ValueError("unsupported secret format")
    n1, wrapped, n2, ct = blob[1:13], blob[13:61], blob[61:73], blob[73:]
    dek = AESGCM(_kek()).decrypt(n1, wrapped, b"xploads-dek")
    return AESGCM(dek).decrypt(n2, ct, associated_data).decode()


# --- TOTP --------------------------------------------------------------------------------------------------


def new_totp_secret() -> str:
    return pyotp.random_base32()


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="XploAds")


def verify_totp(secret: str, code: str) -> bool:
    code = code.strip().replace(" ", "")
    return code.isdigit() and pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_recovery_codes(count: int = 10) -> list[str]:
    return [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(count)]
