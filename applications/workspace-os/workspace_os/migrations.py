from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .platform import ModuleDataStore
from .registry import ModuleDefinition, ModuleRegistry


class ModuleMigrationRunner:
    """Apply safe, declarative snapshot migrations declared by manifests."""

    def __init__(self, store: ModuleDataStore, data_dir: Path) -> None:
        self.store = store
        self.backup_root = data_dir / "migration-backups"

    def migrate(self, module: ModuleDefinition) -> dict[str, Any]:
        snapshot = self.store.get(module.id)
        if snapshot is None:
            return {"ok": True, "moduleId": module.id, "from": module.data_schema_version, "to": module.data_schema_version, "changed": False}
        current = max(1, int(snapshot.get("schemaVersion", 1)))
        target = module.data_schema_version
        if current >= target:
            return {"ok": True, "moduleId": module.id, "from": current, "to": current, "changed": False}

        data = copy.deepcopy(snapshot.get("data"))
        start = current
        steps = {(int(item.get("from", 0)), int(item.get("to", 0))): item for item in module.migrations}
        while current < target:
            candidates = [item for (source, destination), item in steps.items() if source == current and current < destination <= target]
            if not candidates:
                raise ValueError(f"{module.name}: migração ausente da versão {current} para {target}.")
            step = min(candidates, key=lambda item: int(item["to"]))
            data = self._apply_operations(data, step.get("operations", []))
            current = int(step["to"])

        self._backup(module.id, snapshot, start)
        self.store.save(module.id, {"schemaVersion": current, "data": data})
        return {"ok": True, "moduleId": module.id, "from": start, "to": current, "changed": True}

    def migrate_all(self, registry: ModuleRegistry) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for module in registry.modules.values():
            try:
                results.append(self.migrate(module))
            except (OSError, ValueError, TypeError) as exc:
                results.append({"ok": False, "moduleId": module.id, "error": str(exc)})
        return results

    def _backup(self, module_id: str, snapshot: dict[str, Any], version: int) -> None:
        target = self.backup_root / module_id
        target.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = target / f"v{version}-{stamp}.json"
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        backups = sorted(target.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        for old in backups[5:]:
            old.unlink(missing_ok=True)

    @classmethod
    def _apply_operations(cls, data: Any, operations: object) -> Any:
        if not isinstance(operations, list):
            raise ValueError("A lista de operações da migração é inválida.")
        result = copy.deepcopy(data)
        for operation in operations:
            if not isinstance(operation, dict):
                raise ValueError("Operação de migração inválida.")
            kind = str(operation.get("op", ""))
            if kind == "rename":
                value, found = cls._pop_path(result, str(operation.get("from", "")))
                if found:
                    cls._set_path(result, str(operation.get("to", "")), value, overwrite=False)
            elif kind == "default":
                cls._set_path(result, str(operation.get("path", "")), copy.deepcopy(operation.get("value")), overwrite=False)
            elif kind == "remove":
                cls._pop_path(result, str(operation.get("path", "")))
            else:
                raise ValueError(f"Operação de migração não permitida: {kind or '(vazia)'}.")
        return result

    @staticmethod
    def _parts(path: str) -> list[str]:
        parts = [item for item in path.split(".") if item]
        if not parts or any(not item.replace("_", "").replace("-", "").isalnum() for item in parts):
            raise ValueError(f"Caminho de migração inválido: {path!r}.")
        return parts

    @classmethod
    def _pop_path(cls, root: Any, path: str) -> tuple[Any, bool]:
        parts = cls._parts(path)
        current = root
        for part in parts[:-1]:
            if not isinstance(current, dict) or part not in current:
                return None, False
            current = current[part]
        if not isinstance(current, dict) or parts[-1] not in current:
            return None, False
        return current.pop(parts[-1]), True

    @classmethod
    def _set_path(cls, root: Any, path: str, value: Any, *, overwrite: bool) -> None:
        if not isinstance(root, dict):
            raise ValueError("A raiz de dados precisa ser um objeto para esta migração.")
        parts = cls._parts(path)
        current = root
        for part in parts[:-1]:
            child = current.setdefault(part, {})
            if not isinstance(child, dict):
                raise ValueError(f"Não foi possível criar o caminho {path!r}.")
            current = child
        if overwrite or parts[-1] not in current:
            current[parts[-1]] = value
