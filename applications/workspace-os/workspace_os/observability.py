from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class StructuredModuleLogs:
    """Small per-module JSONL logs with rotation and retention."""

    def __init__(self, data_dir: Path, *, max_bytes: int = 2 * 1024 * 1024, backups: int = 3, retention_days: int = 14) -> None:
        self.root = data_dir / "logs" / "modules"
        self.max_bytes = max_bytes
        self.backups = backups
        self.retention_days = retention_days
        self._lock = threading.RLock()
        self.cleanup()

    def write(self, module_id: str, event: str, *, level: str = "info", **fields: Any) -> None:
        safe_id = self._safe_id(module_id)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "moduleId": safe_id or "core",
            "level": level,
            "event": event,
            **{key: value for key, value in fields.items() if value is not None and value != ""},
        }
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            path = self.root / f"{record['moduleId']}.jsonl"
            self._rotate(path)
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def tail(self, module_id: str, limit: int = 100) -> list[dict[str, Any]]:
        path = self.root / f"{self._safe_id(module_id)}.jsonl"
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, min(limit, 500)):]:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
        return rows

    def summary(self) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        return [
            {"moduleId": path.stem, "bytes": path.stat().st_size, "updatedAt": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}
            for path in sorted(self.root.glob("*.jsonl"))
        ]

    def cleanup(self) -> None:
        if not self.root.is_dir():
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        for path in self.root.glob("*.jsonl.*"):
            try:
                if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff:
                    path.unlink()
            except OSError:
                continue

    def _rotate(self, path: Path) -> None:
        try:
            if path.stat().st_size < self.max_bytes:
                return
        except FileNotFoundError:
            return
        oldest = path.with_suffix(path.suffix + f".{self.backups}")
        if oldest.exists():
            oldest.unlink()
        for index in range(self.backups - 1, 0, -1):
            source = path.with_suffix(path.suffix + f".{index}")
            if source.exists():
                source.replace(path.with_suffix(path.suffix + f".{index + 1}"))
        path.replace(path.with_suffix(path.suffix + ".1"))

    @staticmethod
    def _safe_id(module_id: str) -> str:
        value = "".join(character for character in str(module_id) if character.isalnum() or character in "-_")[:64]
        return value or "core"
