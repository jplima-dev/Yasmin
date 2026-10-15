from __future__ import annotations

import json
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import __version__
from .origin import CoreOrigin


MODULE_ID = re.compile(r"^[a-z][a-z0-9-]{1,39}$")


@dataclass(frozen=True)
class ModuleDefinition:
    id: str
    name: str
    vendor: str
    author: str
    category: str
    description: str
    kind: str
    project_path: Path | None
    url: str | None
    service_url: str | None
    health_url: str | None
    command: tuple[str, ...]
    entry_file: str | None
    auto_start: bool
    icon: str
    instructions: tuple[str, ...]
    keywords: tuple[str, ...]
    source: str
    version: str
    min_core_version: str
    permissions: tuple[str, ...]
    capabilities: dict[str, Any]
    data_schema_version: int
    migrations: tuple[dict[str, Any], ...]
    manifest_path: Path | None

    @property
    def installed(self) -> bool:
        return self.project_path is None or self.project_path.exists()


class ModuleRegistry:
    def __init__(self, config_path: Path, ecosystem_root: Path) -> None:
        self.config_path = config_path.resolve()
        self.ecosystem_root = ecosystem_root.resolve()
        self.discovery_errors: list[str] = []
        self.core_origin = CoreOrigin.load(self.config_path)
        self.trusted_command_modules: set[str] = set()
        self.module_order: list[str] = []
        self.modules = self._load()

    def _load(self) -> dict[str, ModuleDefinition]:
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("config/modules.json precisa conter um objeto JSON.")
        entries = payload.get("modules", [])
        if not isinstance(entries, list):
            raise ValueError("config/modules.json precisa conter uma lista modules.")
        trusted = payload.get("trustedCommandModules", [])
        order = payload.get("moduleOrder", [])
        if isinstance(trusted, list):
            self.trusted_command_modules = {str(item) for item in trusted if MODULE_ID.fullmatch(str(item))}
        if isinstance(order, list):
            self.module_order = [str(item) for item in order if MODULE_ID.fullmatch(str(item))]
        modules: dict[str, ModuleDefinition] = {}
        for index, raw in enumerate(entries):
            try:
                module = self._definition(raw, base_path=self.config_path.parent.parent, source="legacy-registry")
                if module.id in modules:
                    raise ValueError(f"ID de módulo duplicado: {module.id}")
                modules[module.id] = module
            except (OSError, ValueError) as exc:
                self.discovery_errors.append(f"{self.config_path}#modules[{index}]: {exc}")
        self._discover(modules)
        position = {module_id: index for index, module_id in enumerate(self.module_order)}
        return dict(sorted(modules.items(), key=lambda item: (position.get(item[0], len(position)), item[1].name.lower())))

    def _discover(self, modules: dict[str, ModuleDefinition]) -> None:
        """Load isolated module contracts from direct ecosystem children."""
        for manifest in sorted(self.ecosystem_root.glob("*/ink-module.json")):
            try:
                raw = json.loads(manifest.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise ValueError("o manifesto precisa conter um objeto JSON")
                module_id = str(raw.get("id", ""))
                has_privileged_contract = bool(raw.get("command") or raw.get("autoStart"))
                if has_privileged_contract and module_id not in self.trusted_command_modules:
                    raise ValueError("o manifesto solicita execução, mas o módulo não está na lista central de confiança")
                normalized = {**raw, "path": "."}
                module = self._definition(normalized, base_path=manifest.parent, source="manifest", manifest_path=manifest)
                if module.kind not in {"static-web", "web-service", "remote-web", "desktop", "planned"}:
                    raise ValueError("kind de módulo não reconhecido")
                previous = modules.get(module.id)
                if previous and previous.project_path != module.project_path:
                    raise ValueError(f"ID duplicado também declarado por {previous.project_path}")
                modules[module.id] = module
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                self.discovery_errors.append(f"{manifest}: {exc}")

    def _definition(self, raw: object, *, base_path: Path, source: str, manifest_path: Path | None = None) -> ModuleDefinition:
        if not isinstance(raw, dict):
            raise ValueError("Cada módulo precisa ser um objeto JSON.")
        module_id = raw.get("id", "")
        if not isinstance(module_id, str) or not MODULE_ID.fullmatch(module_id):
            raise ValueError(f"ID de módulo inválido: {module_id!r}")
        relative_path = raw.get("path")
        project_path = None
        if relative_path:
            project_path = (base_path / str(relative_path)).resolve()
            try:
                project_path.relative_to(self.ecosystem_root)
            except ValueError as exc:
                raise ValueError(f"O módulo {module_id} aponta para fora do ecossistema.") from exc
        entry_file = raw.get("entryFile")
        if entry_file is not None:
            if not isinstance(entry_file, str) or not entry_file.strip() or project_path is None:
                raise ValueError(f"Arquivo inicial inválido no módulo {module_id}.")
            try:
                (project_path / entry_file).resolve().relative_to(project_path)
            except ValueError as exc:
                raise ValueError(f"O arquivo inicial de {module_id} aponta para fora da pasta.") from exc
        command = raw.get("command", [])
        if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
            raise ValueError(f"Comando inválido no módulo {module_id}.")
        if "autoStart" in raw and not isinstance(raw["autoStart"], bool):
            raise ValueError(f"autoStart precisa ser booleano no módulo {module_id}.")
        for field in ("url", "serviceUrl", "healthUrl"):
            value = raw.get(field)
            if value is None:
                continue
            if not isinstance(value, str):
                raise ValueError(f"{field} inválida no módulo {module_id}.")
            parsed_url = urlparse(value)
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
                raise ValueError(f"{field} precisa ser HTTP ou HTTPS no módulo {module_id}.")
            try:
                port = parsed_url.port
            except ValueError as exc:
                raise ValueError(f"{field} possui porta inválida no módulo {module_id}.") from exc
            if port is not None and not 1 <= port <= 65535:
                raise ValueError(f"{field} possui porta inválida no módulo {module_id}.")
        permissions = raw.get("permissions", [])
        if not isinstance(permissions, list) or not all(isinstance(item, str) for item in permissions):
            raise ValueError(f"Permissões inválidas no módulo {module_id}.")
        capabilities = raw.get("capabilities", {})
        if not isinstance(capabilities, dict):
            raise ValueError(f"Recursos inválidos no módulo {module_id}.")
        for field in ("export", "import", "print", "offline"):
            if field in capabilities and not isinstance(capabilities[field], bool):
                raise ValueError(f"capabilities.{field} precisa ser booleano no módulo {module_id}.")
        shortcuts = capabilities.get("shortcuts", [])
        if not isinstance(shortcuts, list) or not all(isinstance(item, str) for item in shortcuts):
            raise ValueError(f"Atalhos de recursos inválidos no módulo {module_id}.")
        capability_permissions = capabilities.get("permissions", permissions)
        if not isinstance(capability_permissions, list) or not all(isinstance(item, str) for item in capability_permissions):
            raise ValueError(f"Permissões de recursos inválidas no módulo {module_id}.")
        normalized_capabilities = {
            "export": bool(capabilities.get("export", False)),
            "import": bool(capabilities.get("import", False)),
            "print": bool(capabilities.get("print", False)),
            "offline": bool(capabilities.get("offline", raw.get("kind") == "static-web")),
            "shortcuts": list(dict.fromkeys(shortcuts)),
            "permissions": list(dict.fromkeys(capability_permissions)),
        }
        migrations = raw.get("migrations", [])
        if not isinstance(migrations, list) or not all(isinstance(item, dict) for item in migrations):
            raise ValueError(f"Migrações inválidas no módulo {module_id}.")
        instructions = raw.get("instructions", [])
        keywords = raw.get("keywords", [])
        if not isinstance(instructions, list) or not all(isinstance(item, str) for item in instructions):
            raise ValueError(f"Instruções inválidas no módulo {module_id}.")
        if not isinstance(keywords, list) or not all(isinstance(item, str) for item in keywords):
            raise ValueError(f"Palavras-chave inválidas no módulo {module_id}.")
        try:
            data_schema_version = max(1, int(raw.get("dataSchemaVersion", 1)))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Versão de dados inválida no módulo {module_id}.") from exc
        return ModuleDefinition(
            id=module_id,
            name=str(raw.get("name", module_id)),
            vendor=str(raw.get("vendor", "")),
            author=str(raw.get("author", "")),
            category=str(raw.get("category", "utilities")),
            description=str(raw.get("description", "")),
            kind=str(raw.get("kind", "planned")),
            project_path=project_path,
            url=raw.get("url"),
            service_url=raw.get("serviceUrl"),
            health_url=raw.get("healthUrl"),
            command=tuple(command),
            entry_file=entry_file,
            auto_start=bool(raw.get("autoStart", False)),
            icon=str(raw.get("icon", "app")),
            instructions=tuple(instructions),
            keywords=tuple(keywords),
            source=source,
            version=str(raw.get("version", "")),
            min_core_version=str(raw.get("minCoreVersion", "")),
            permissions=tuple(normalized_capabilities["permissions"]),
            capabilities=normalized_capabilities,
            data_schema_version=data_schema_version,
            migrations=tuple(dict(item) for item in migrations),
            manifest_path=manifest_path,
        )

    def get(self, module_id: str) -> ModuleDefinition:
        try:
            return self.modules[module_id]
        except KeyError as exc:
            raise KeyError(f"Módulo desconhecido: {module_id}") from exc

    @staticmethod
    def is_reachable(url: str | None, timeout: float = 0.18) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError:
            return False
        try:
            with socket.create_connection((parsed.hostname, port), timeout=timeout):
                return True
        except OSError:
            return False

    def serialize(self, custom_urls: dict[str, str] | None = None, origin: str | None = None) -> list[dict[str, Any]]:
        custom_urls = custom_urls or {}
        origin = (origin or self.core_origin.url).rstrip("/")
        result = []
        for module in self.modules.values():
            url = custom_urls.get(module.id) or module.url
            if not url and module.entry_file and module.project_path:
                url = f"{origin}/module/{module.id}/{module.entry_file}"
            health_url = custom_urls.get(module.id) or module.health_url or url
            reachable = self.is_reachable(health_url)
            result.append(
                {
                    "id": module.id,
                    "name": module.name,
                    "vendor": module.vendor,
                    "author": module.author,
                    "category": module.category,
                    "description": module.description,
                    "kind": module.kind,
                    "installed": module.installed,
                    "reachable": reachable,
                    "url": url,
                    "serviceUrl": module.service_url,
                    "canStart": bool(module.command and module.installed),
                    "autoStartDefault": module.auto_start,
                    "icon": module.icon,
                    "instructions": list(module.instructions),
                    "keywords": list(module.keywords),
                    "source": module.source,
                    "version": module.version,
                    "minCoreVersion": module.min_core_version,
                    "compatible": not module.min_core_version or _version_tuple(__version__) >= _version_tuple(module.min_core_version),
                    "permissions": list(module.permissions),
                    "capabilities": module.capabilities,
                    "dataSchemaVersion": module.data_schema_version,
                }
            )
        return result


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value)
    return tuple(int(part) for part in parts[:3]) or (0,)
