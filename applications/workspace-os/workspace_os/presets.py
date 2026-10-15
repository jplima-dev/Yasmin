from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


class PresetStore:
    def __init__(self, data_dir: Path, *, max_items: int = 200) -> None:
        self.path = (data_dir / "presets.json").resolve()
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
            return list(self._load())

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name", "")).strip()[:120]
        if not name:
            raise ValueError("O preset precisa de um nome.")
        module_ids = payload.get("moduleIds", [])
        data = payload.get("data", {})
        if not isinstance(module_ids, list) or not all(isinstance(item, str) for item in module_ids):
            raise ValueError("moduleIds precisa ser uma lista de IDs.")
        if not isinstance(data, dict):
            raise ValueError("Os dados do preset precisam ser um objeto.")
        serialized = json.dumps(data, ensure_ascii=False)
        if len(serialized.encode("utf-8")) > 128 * 1024:
            raise ValueError("O preset excede o limite de 128 KiB.")
        preset_id = str(payload.get("id", "")).strip()
        if preset_id and any(character not in "0123456789abcdef" for character in preset_id.lower()):
            raise ValueError("ID de preset inválido.")
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            items = self._load()
            previous = next((item for item in items if item.get("id") == preset_id), None)
            item = {
                "id": preset_id or uuid4().hex,
                "name": name,
                "description": str(payload.get("description", "")).strip()[:500],
                "moduleIds": list(dict.fromkeys(item[:100] for item in module_ids)),
                "data": data,
                "createdAt": previous.get("createdAt", now) if previous else now,
                "updatedAt": now,
            }
            remaining = [current for current in items if current.get("id") != item["id"]]
            self._write([item, *remaining][: self.max_items])
            return item

    def remove(self, preset_id: str) -> bool:
        with self._lock:
            items = self._load()
            remaining = [item for item in items if item.get("id") != preset_id]
            if len(remaining) == len(items):
                return False
            self._write(remaining)
            return True
