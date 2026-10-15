from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_PERMISSIONS = {
    "remote_ring": True,
    "remote_lock": False,
    "screen_share": False,
    "remote_actions": False,
    "photos": False,
    "clipboard": False,
}


class IntegrationProfiles:
    """Adapters for configuration owned by independent device projects."""

    def __init__(self, bridge_agent_dir: Path | None = None) -> None:
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Bridge"
        self.bridge_agent_dir = (bridge_agent_dir or base).resolve()
        self.bridge_agent_path = self.bridge_agent_dir / "agent.json"

    def bridge_agent(self) -> dict[str, Any]:
        raw: dict[str, Any] = {}
        if self.bridge_agent_path.is_file():
            try:
                payload = json.loads(self.bridge_agent_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    raw = payload
            except (OSError, json.JSONDecodeError):
                raw = {}
        permissions = {**DEFAULT_PERMISSIONS, **raw.get("permissions", {})}
        return {
            "server": str(raw.get("server", "http://127.0.0.1:8876")),
            "name": str(raw.get("name", socket.gethostname())),
            "paired": bool(raw.get("device_id")),
            "clipboard_enabled": bool(raw.get("clipboard_enabled", False)),
            "permissions": {key: bool(permissions.get(key)) for key in DEFAULT_PERMISSIONS},
        }

    def update_bridge_agent(self, changes: dict[str, Any]) -> dict[str, Any]:
        allowed = {"server", "name", "clipboard_enabled", "permissions"}
        if set(changes) - allowed:
            raise ValueError("O perfil do agente contém campos desconhecidos.")
        server = str(changes.get("server", "http://127.0.0.1:8876")).strip().rstrip("/")
        parsed = urlparse(server)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Endereço do Bridge Agent inválido.")
        name = str(changes.get("name", socket.gethostname())).strip()
        if not name or len(name) > 80:
            raise ValueError("O nome do agente precisa ter entre 1 e 80 caracteres.")
        permissions_value = changes.get("permissions", {})
        if not isinstance(permissions_value, dict) or any(
            key not in DEFAULT_PERMISSIONS or not isinstance(value, bool)
            for key, value in permissions_value.items()
        ):
            raise ValueError("Permissões do agente inválidas.")
        existing: dict[str, Any] = {}
        if self.bridge_agent_path.is_file():
            try:
                payload = json.loads(self.bridge_agent_path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    existing = payload
            except (OSError, json.JSONDecodeError):
                existing = {}
        permissions = {**DEFAULT_PERMISSIONS, **existing.get("permissions", {}), **permissions_value}
        clipboard = bool(changes.get("clipboard_enabled", False))
        permissions["clipboard"] = clipboard
        updated = {
            **existing,
            "server": server,
            "name": name,
            "clipboard_enabled": clipboard,
            "permissions": permissions,
        }
        self.bridge_agent_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.bridge_agent_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.bridge_agent_path)
        return self.bridge_agent()
