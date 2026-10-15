from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CoreOrigin:
    """Single source of truth for the local Core address."""

    host: str = "127.0.0.1"
    port: int = 8790
    scheme: str = "http"

    @property
    def url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}"

    @classmethod
    def load(cls, config_path: Path) -> "CoreOrigin":
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        raw = payload.get("origin", {}) if isinstance(payload, dict) else {}
        if not isinstance(raw, dict):
            return cls()
        host = str(raw.get("host", cls.host)).strip()
        scheme = str(raw.get("scheme", cls.scheme)).strip().lower()
        try:
            port = int(raw.get("port", cls.port))
        except (TypeError, ValueError):
            port = cls.port
        if host not in {"127.0.0.1", "localhost", "::1"}:
            host = cls.host
        # The built-in server does not terminate TLS; accepting https here would
        # make health checks and every generated module URL unusable.
        if scheme != "http":
            scheme = cls.scheme
        if not 1 <= port <= 65535:
            port = cls.port
        return cls(host=host, port=port, scheme=scheme)
