from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class BlackBoxStore:
    KINDS = {"error", "request", "file", "change", "process"}
    LEVELS = {"info", "warning", "error"}

    def __init__(self, data_dir: Path, *, max_items: int = 500) -> None:
        self.path = (data_dir / "blackbox.json").resolve()
        self.max_items = max_items
        self._lock = threading.RLock()

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return payload if isinstance(payload, list) else []

    def _write(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def list(self, *, limit: int = 150) -> list[dict[str, Any]]:
        with self._lock:
            return self._load()[: max(1, min(limit, self.max_items))]

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        kind = str(payload.get("kind", "error")).lower()
        level = str(payload.get("level", "error")).lower()
        if kind not in self.KINDS or level not in self.LEVELS:
            raise ValueError("Evento da caixa-preta inválido.")
        title = str(payload.get("title", "")).strip()[:180]
        if not title:
            raise ValueError("O evento precisa de um título.")
        event = {
            "id": uuid4().hex,
            "kind": kind,
            "level": level,
            "title": title,
            "detail": str(payload.get("detail", "")).strip()[:2000],
            "moduleId": str(payload.get("moduleId", "")).strip()[:100],
            "path": str(payload.get("path", "")).strip()[:1000],
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._write([event, *self._load()][: self.max_items])
        return event

    def clear(self) -> int:
        with self._lock:
            count = len(self._load())
            self._write([])
            return count
