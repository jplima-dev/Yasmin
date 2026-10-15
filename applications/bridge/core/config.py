from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("BRIDGE_DATA_DIR", ROOT / ".data"))
    received_dir: Path = Path(os.getenv("BRIDGE_RECEIVED_DIR", ROOT / "received"))
    host: str = os.getenv("BRIDGE_HOST", "0.0.0.0")
    port: int = int(os.getenv("BRIDGE_PORT", "8876"))
    public_url: str = os.getenv("BRIDGE_PUBLIC_URL", "http://127.0.0.1:8876")
    tls_cert: str | None = os.getenv("BRIDGE_TLS_CERT")
    tls_key: str | None = os.getenv("BRIDGE_TLS_KEY")
    discovery_port: int = int(os.getenv("BRIDGE_DISCOVERY_PORT", "48765"))
    max_chunk_bytes: int = int(os.getenv("BRIDGE_MAX_CHUNK", str(4 * 1024 * 1024)))

    def prepare(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.received_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "chunks").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "drive2-outbox").mkdir(parents=True, exist_ok=True)


settings = Settings()
