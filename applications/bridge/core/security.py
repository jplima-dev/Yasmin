from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


SENSITIVE_ACTIONS = {"lock", "screen_start", "delete", "settings_change"}


class DeviceIdentity:
    """Identidade Ed25519 persistente do Bridge Core/agent."""

    def __init__(self, private_key: Ed25519PrivateKey):
        self._key = private_key

    @classmethod
    def load_or_create(cls, path: Path) -> "DeviceIdentity":
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            key = serialization.load_pem_private_key(path.read_bytes(), password=None)
            if not isinstance(key, Ed25519PrivateKey):
                raise ValueError("A identidade armazenada não é Ed25519")
            return cls(key)
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        path.write_bytes(pem)
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return cls(key)

    @property
    def public_key(self) -> str:
        raw = self._key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        return base64.urlsafe_b64encode(raw).decode()

    @property
    def fingerprint(self) -> str:
        digest = hashlib.sha256(self.public_key.encode()).hexdigest().upper()
        return ":".join(digest[i : i + 4] for i in range(0, 24, 4))

    def sign(self, payload: dict) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(self._key.sign(canonical)).decode()


def short_pairing_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


@dataclass
class Confirmation:
    token: str
    actor_id: str
    action: str
    target_id: str
    expires_at: float


class ActionGate:
    """Segundo passo explícito para comandos sensíveis; tokens são de uso único."""

    def __init__(self) -> None:
        self._pending: dict[str, Confirmation] = {}

    def request(self, actor_id: str, action: str, target_id: str, ttl: int = 120) -> Confirmation:
        token = secrets.token_urlsafe(24)
        item = Confirmation(token, actor_id, action, target_id, time.time() + ttl)
        self._pending[token] = item
        return item

    def consume(self, token: str, actor_id: str, action: str, target_id: str) -> bool:
        item = self._pending.pop(token, None)
        if not item or item.expires_at < time.time():
            return False
        return (item.actor_id, item.action, item.target_id) == (actor_id, action, target_id)

