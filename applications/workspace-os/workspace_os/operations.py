from __future__ import annotations

import threading
import time


class OperationGate:
    """Reject concurrent mutations and replayed idempotency keys."""

    def __init__(self, replay_ttl: int = 300) -> None:
        self.replay_ttl = replay_ttl
        self._active: set[str] = set()
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def acquire(self, operation: str, idempotency_key: str = "") -> tuple[bool, str]:
        now = time.monotonic()
        fingerprint = f"{operation}\0{idempotency_key}" if idempotency_key else ""
        with self._lock:
            self._seen = {key: expiry for key, expiry in self._seen.items() if expiry > now}
            if operation in self._active:
                return False, "Uma operação equivalente já está em andamento."
            if fingerprint and fingerprint in self._seen:
                return False, "Esta solicitação já foi processada."
            self._active.add(operation)
            if fingerprint:
                self._seen[fingerprint] = now + self.replay_ttl
            return True, ""

    def release(self, operation: str) -> None:
        with self._lock:
            self._active.discard(operation)
