from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4


class ActivityStore:
    """Small persistent event log shared by every Workspace origin."""

    LEVELS = {"info", "success", "warning", "error"}
    KINDS = {"system", "module", "file", "export", "terminal", "backup"}

    def __init__(self, data_dir: Path, *, max_items: int = 250) -> None:
        self.path = (data_dir / "activity.json").resolve()
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

    def list(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._load()[: max(1, min(limit, self.max_items))])

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload.get("title", "")).strip()[:160]
        if not title:
            raise ValueError("A atividade precisa de um título.")
        level = str(payload.get("level", "info")).lower()
        kind = str(payload.get("kind", "system")).lower()
        if level not in self.LEVELS:
            raise ValueError("Nível de atividade inválido.")
        if kind not in self.KINDS:
            raise ValueError("Tipo de atividade inválido.")
        url = str(payload.get("url", "")).strip()[:1000]
        if url and urlparse(url).scheme not in {"http", "https"}:
            raise ValueError("Endereço da atividade inválido.")
        actions_payload = payload.get("actions", [])
        if not isinstance(actions_payload, list):
            raise ValueError("As ações da atividade precisam ser uma lista.")
        actions = []
        for action in actions_payload[:3]:
            if not isinstance(action, dict):
                continue
            action_url = str(action.get("url", "")).strip()[:1000]
            label = str(action.get("label", "")).strip()[:60]
            if not label or not action_url or urlparse(action_url).scheme not in {"http", "https"}:
                continue
            actions.append({"label": label, "url": action_url})
        item = {
            "id": uuid4().hex,
            "title": title,
            "detail": str(payload.get("detail", "")).strip()[:1000],
            "level": level,
            "kind": kind,
            "moduleId": str(payload.get("moduleId", "")).strip()[:100],
            "url": url,
            "actions": actions,
            "read": bool(payload.get("read", False)),
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            items = [item, *self._load()][: self.max_items]
            self._write(items)
        return item

    def mark_all_read(self) -> int:
        with self._lock:
            items = self._load()
            changed = 0
            for item in items:
                if not item.get("read"):
                    item["read"] = True
                    changed += 1
            if changed:
                self._write(items)
            return changed

    def clear(self) -> int:
        with self._lock:
            count = len(self._load())
            self._write([])
            return count

    def remove(self, item_id: str) -> bool:
        with self._lock:
            items = self._load()
            remaining = [item for item in items if item.get("id") != item_id]
            if len(remaining) == len(items):
                return False
            self._write(remaining)
            return True
