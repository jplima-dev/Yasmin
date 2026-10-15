from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class ClipboardStore:
    def __init__(self, data_dir: Path, *, max_items: int = 100) -> None:
        self.path = (data_dir / "clipboard.json").resolve()
        self.max_items = max_items
        self._lock = threading.RLock()

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return value if isinstance(value, list) else []

    def _write(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            items = self._load()
            pinned = sorted((item for item in items if item.get("pinned")), key=lambda item: str(item.get("createdAt", "")), reverse=True)
            regular = sorted((item for item in items if not item.get("pinned")), key=lambda item: str(item.get("createdAt", "")), reverse=True)
            return [*pinned, *regular]

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = str(payload.get("text", ""))
        if not text.strip():
            raise ValueError("A área de transferência não aceita texto vazio.")
        if len(text.encode("utf-8")) > 256 * 1024:
            raise ValueError("O texto excede o limite de 256 KiB.")
        item = {
            "id": uuid4().hex,
            "text": text,
            "label": str(payload.get("label", "")).strip()[:120],
            "source": str(payload.get("source", "")).strip()[:100],
            "pinned": bool(payload.get("pinned", False)),
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            items = [item, *[current for current in self._load() if current.get("text") != text]]
            pinned = [current for current in items if current.get("pinned")]
            regular = [current for current in items if not current.get("pinned")][: self.max_items]
            self._write([*pinned, *regular][: self.max_items])
        return item

    def pin(self, item_id: str, pinned: bool) -> dict[str, Any]:
        with self._lock:
            items = self._load()
            item = next((current for current in items if current.get("id") == item_id), None)
            if not item:
                raise KeyError("Item da área de transferência não encontrado.")
            item["pinned"] = bool(pinned)
            self._write(items)
            return item

    def remove(self, item_id: str) -> bool:
        with self._lock:
            items = self._load()
            remaining = [item for item in items if item.get("id") != item_id]
            if len(remaining) == len(items):
                return False
            self._write(remaining)
            return True
