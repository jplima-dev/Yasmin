from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

from app.config import settings

PBKDF2_ROUNDS = 310_000


def hash_password(password: str, salt: bytes | None = None) -> str:
    if len(password) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres.")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, rounds, salt_b64, digest_b64 = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _secret() -> bytes:
    if not settings.auth_secret:
        raise RuntimeError("DRIVE2_AUTH_SECRET não configurado.")
    return settings.auth_secret.encode()


def create_session(username: str) -> str:
    expires = int(time.time() + settings.auth_session_hours * 3600)
    nonce = secrets.token_urlsafe(8)
    payload = f"{username}|{expires}|{nonce}"
    signature = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{signature}".encode()).decode()


def verify_session(token: str | None) -> bool:
    if not token:
        return False
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        username, expires, nonce, signature = decoded.split("|", 3)
        payload = f"{username}|{expires}|{nonce}"
        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        return username == settings.auth_username and int(expires) >= int(time.time()) and hmac.compare_digest(signature, expected)
    except Exception:
        return False
