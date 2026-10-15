from __future__ import annotations

import json
import http.client
import mimetypes
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import __version__
from .activity import ActivityStore
from .clipboard import ClipboardStore
from .blackbox import BlackBoxStore
from .dropzone import DropzoneStore
from .integrations import IntegrationProfiles
from .migrations import ModuleMigrationRunner
from .observability import StructuredModuleLogs
from .operations import OperationGate
from .origin import CoreOrigin
from .processes import ProcessManager
from .presets import PresetStore
from .platform import GitProjects, ModuleDataStore, PortableArchive, module_audit
from .registry import ModuleRegistry
from .settings import SettingsStore, effective_module_urls
from .security import SessionAuth, TerminalPolicy
from .startup import WindowsStartup
from .terminal import TerminalExecutionManager


YASMIN_BRIDGE_PORT = 45456

PYTHON_COMMAND = re.compile(r"^python(?:3(?:\.\d+)?)?(?=\s|$)", re.IGNORECASE)
PIP_COMMAND = re.compile(r"^pip(?:3(?:\.\d+)?)?(?=\s|$)", re.IGNORECASE)
PYTHON_PRINT_EXPRESSION = re.compile(r"^print\s*\(", re.IGNORECASE)
QUOTED_PATH = re.compile(r"[\"']([^\"']+)[\"']")
BARE_PATH = re.compile(r"(?<![\w])((?:[A-Za-z]:[\\/]|\\\\|\.\.[\\/])[^\s|;&<>]+)")
ENV_PATH = re.compile(r"(?<![\w])((?:\$env:[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%|~[\\/])[^\s|;&<>]*)", re.IGNORECASE)


def decode_terminal_output(value: bytes | str | None, windows_encoding: str | None = None) -> str:
    """Decode shell output, including legacy Windows console programs."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        pass

    if windows_encoding:
        try:
            return value.decode(windows_encoding)
        except (LookupError, UnicodeDecodeError):
            pass
    if os.name == "nt":
        for encoding in ("mbcs", "oem"):
            try:
                return value.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                pass
    return value.decode("utf-8", errors="replace")


def uses_legacy_windows_encoding(command: str) -> bool:
    """Return whether a simple command resolves to a legacy Windows utility."""
    if os.name != "nt" or not os.environ.get("SystemRoot"):
        return False
    if any(operator in command for operator in ("|", ";", "&")):
        return False
    match = re.match(r"^([A-Za-z0-9_.-]+)", command.lstrip())
    if not match:
        return False
    executable = shutil.which(match.group(1))
    if not executable:
        return False
    try:
        return Path(executable).resolve().is_relative_to(Path(os.environ["SystemRoot"]).resolve())
    except OSError:
        return False


def find_python(cwd: Path) -> Path | None:
    """Prefer a project interpreter, then an interpreter installed on the PC."""
    local_candidates = (
        cwd / ".venv" / "Scripts" / "python.exe",
        cwd / "venv" / "Scripts" / "python.exe",
        cwd / "env" / "Scripts" / "python.exe",
        cwd / ".venv" / "bin" / "python",
        cwd / "venv" / "bin" / "python",
        cwd / "python.exe",
    )
    for candidate in local_candidates:
        if candidate.is_file():
            return candidate.resolve()

    discovered: list[str | None] = []
    if Path(sys.executable).stem.lower().startswith("python"):
        discovered.append(sys.executable)
    discovered.extend(shutil.which(name) for name in ("python.exe", "python", "python3.exe", "python3"))
    for value in discovered:
        if not value:
            continue
        candidate = Path(value).resolve()
        if "windowsapps" in {part.lower() for part in candidate.parts}:
            continue
        if candidate.is_file():
            return candidate

    roots: list[Path] = []
    if os.environ.get("LOCALAPPDATA"):
        roots.append(Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Python")
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(variable):
            roots.append(Path(os.environ[variable]))
    candidates: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        candidates.extend(root.glob("Python*/python.exe"))
    return max(candidates, key=lambda item: item.parent.name, default=None)


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def external_path_reference(command: str, cwd: Path, ecosystem_root: Path) -> Path | None:
    """Find explicit absolute or parent-relative paths that escape the workspace root."""
    candidates = [*QUOTED_PATH.findall(command), *BARE_PATH.findall(command), *ENV_PATH.findall(command)]
    for raw in candidates:
        expanded = re.sub(
            r"\$env:([A-Za-z_][A-Za-z0-9_]*)",
            lambda match: os.environ.get(match.group(1), match.group(0)),
            os.path.expandvars(raw.strip().rstrip(",)")),
            flags=re.IGNORECASE,
        )
        looks_like_path = (
            Path(expanded).is_absolute()
            or expanded.startswith(("..\\", "../", "\\\\"))
            or bool(re.match(r"^[A-Za-z]:[\\/]", expanded))
        )
        if not looks_like_path:
            continue
        candidate = Path(expanded).expanduser()
        try:
            resolved = (candidate if candidate.is_absolute() else cwd / candidate).resolve()
            resolved.relative_to(ecosystem_root.resolve())
        except ValueError:
            return resolved
        except OSError:
            continue
    return None


@dataclass
class AppContext:
    workspace_root: Path
    web_root: Path
    design_root: Path
    registry: ModuleRegistry
    settings: SettingsStore
    processes: ProcessManager
    startup: WindowsStartup
    dropzone: DropzoneStore
    activity: ActivityStore
    presets: PresetStore
    clipboard: ClipboardStore
    integrations: IntegrationProfiles
    module_data: ModuleDataStore
    portable: PortableArchive
    git: GitProjects
    blackbox: BlackBoxStore
    auth: SessionAuth | None = None
    operation_gate: OperationGate | None = None
    terminal_policy: TerminalPolicy | None = None
    logs: StructuredModuleLogs | None = None
    migrations: ModuleMigrationRunner | None = None
    terminal_executions: TerminalExecutionManager | None = None


class WorkspaceServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], context: AppContext) -> None:
        self.context = context
        self.context.auth = self.context.auth or SessionAuth()
        self.context.operation_gate = self.context.operation_gate or OperationGate()
        self.context.terminal_policy = self.context.terminal_policy or TerminalPolicy()
        self.context.logs = self.context.logs or StructuredModuleLogs(self.context.settings.data_dir)
        self.context.migrations = self.context.migrations or ModuleMigrationRunner(self.context.module_data, self.context.settings.data_dir)
        self.context.terminal_executions = self.context.terminal_executions or TerminalExecutionManager(
            self.context.registry.ecosystem_root, self.context.logs,
        )
        self.context.processes.structured_logs = self.context.logs
        super().__init__(address, WorkspaceRequestHandler)

    def server_close(self) -> None:
        self.context.terminal_executions.cancel_all()
        super().server_close()


class WorkspaceRequestHandler(BaseHTTPRequestHandler):
    server: WorkspaceServer
    protocol_version = "HTTP/1.1"

    def handle_one_request(self) -> None:
        self._response_started = False
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionError):
            self.close_connection = True
        except Exception as exc:
            self._trace(
                "error", "Falha inesperada ao processar uma solicitação",
                detail=f"{type(exc).__name__}: {exc}",
                path=getattr(self, "path", ""), level="error",
            )
            if not self._response_started and not self.wfile.closed:
                try:
                    self._json(
                        {"error": "O Workspace encontrou uma falha interna. Consulte Diagnóstico > Caixa-preta."},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                except (BrokenPipeError, ConnectionError, OSError):
                    self.close_connection = True
            else:
                self.close_connection = True

    def send_response(self, code: int, message: str | None = None) -> None:
        self._response_started = True
        super().send_response(code, message)

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/driver-remote/"):
            if not self._trusted_request():
                self._json({"error": "Origem não autorizada."}, HTTPStatus.FORBIDDEN)
                return
            self._proxy_driver_request()
            return
        if parsed.path == "/api/health":
            self._json({"status": "ok", "version": __version__, "origin": self.server.context.registry.core_origin.url})
            return
        if parsed.path == "/api/yasmin/health":
            self._proxy_yasmin("GET", "/health")
            return
        if parsed.path == "/api/session":
            if not self._trusted_request():
                self._json({"error": "Origem não autorizada."}, HTTPStatus.FORBIDDEN)
                return
            auth = self.server.context.auth
            self._json({"token": auth.token, "expiresAt": auth.expires_at, "origin": self.server.context.registry.core_origin.url})
            return
        if parsed.path == "/api/runtime":
            origin = self.server.context.registry.core_origin
            self._json({"origin": origin.url, "host": origin.host, "port": origin.port, "version": __version__})
            return
        if parsed.path == "/api/modules":
            settings = self.server.context.settings.load()
            modules = self.server.context.registry.serialize(effective_module_urls(settings))
            disabled = set(settings.get("disabled_modules", []))
            for module in modules:
                module["managedState"] = self.server.context.processes.managed_state(str(module["id"]))
                module["autoStart"] = module["id"] in settings["auto_start_modules"]
                module["enabled"] = module["id"] not in disabled
                if module["id"] == "drive2" and not settings["module_configs"]["drive2"].get("run_local", True):
                    module["canStart"] = False
                    module["serviceUrl"] = module["url"]
                    module["url"] = "/module/drive2/web/index.html"
                if not module["enabled"]:
                    module["canStart"] = False
            self._json({"modules": modules})
            return
        if parsed.path == "/api/modules/capabilities":
            self._json({"modules": [
                {"id": module.id, "capabilities": module.capabilities, "permissions": list(module.permissions)}
                for module in self.server.context.registry.modules.values()
            ]})
            return
        if parsed.path == "/api/modules/audit":
            settings = self.server.context.settings.load()
            self._json(module_audit(
                self.server.context.registry,
                self.server.context.processes,
                effective_module_urls(settings),
            ))
            return
        if parsed.path == "/api/modules/git":
            projects = []
            for module in self.server.context.registry.modules.values():
                try:
                    projects.append(self.server.context.git.status(module))
                except (OSError, ValueError, RuntimeError) as exc:
                    projects.append({"available": False, "moduleId": module.id, "error": str(exc)})
                    self.server.context.logs.write(module.id, "git.status.failed", level="error", error=str(exc))
            self._json({"projects": projects})
            return
        if parsed.path == "/api/module-data":
            self._json({"items": self.server.context.module_data.list()})
            return
        if parsed.path.startswith("/api/module-data/"):
            module_id = unquote(parsed.path.removeprefix("/api/module-data/")).strip("/")
            snapshot = self.server.context.module_data.get(module_id)
            if snapshot is None:
                self._json({"error": "Snapshot não encontrado."}, HTTPStatus.NOT_FOUND)
            else:
                self._json(snapshot)
            return
        if parsed.path == "/api/portable/export":
            sections = set(parse_qs(parsed.query).get("sections", [""])[0].split(","))
            content = self.server.context.portable.export(sections)
            stamp = datetime.now().strftime("%Y-%m-%d")
            self._binary(content, "application/zip", f"ink-workspace-portable-{stamp}.zip")
            return
        if parsed.path == "/api/settings":
            self._json(self.server.context.settings.load())
            return
        if parsed.path == "/api/integrations/bridge-agent":
            self._json(self.server.context.integrations.bridge_agent())
            return
        if parsed.path == "/api/startup":
            self._json(self.server.context.startup.status())
            return
        if parsed.path == "/api/diagnostics":
            self._json(self._diagnostics())
            return
        if parsed.path == "/api/activity":
            self._json({"items": self.server.context.activity.list()})
            return
        if parsed.path == "/api/blackbox":
            self._json({"items": self.server.context.blackbox.list()})
            return
        if parsed.path == "/api/presets":
            self._json({"items": self.server.context.presets.list()})
            return
        if parsed.path == "/api/clipboard":
            self._json({"items": self.server.context.clipboard.list()})
            return
        if parsed.path == "/api/dropzone/history":
            self._json({"items": self.server.context.dropzone.history()})
            return
        if parsed.path.startswith("/api/dropzone/folders/"):
            parts = [unquote(item) for item in parsed.path.strip("/").split("/")]
            try:
                if len(parts) == 4:
                    self._json(self.server.context.dropzone.folder_manifest(parts[3]))
                    return
                if len(parts) == 7 and parts[4] == "files" and parts[6] == "content":
                    record, path = self.server.context.dropzone.get_folder_file(parts[3], parts[5])
                    self._serve_file_path(record, path)
                    return
            except KeyError:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
        if parsed.path.startswith("/api/dropzone/files/") and parsed.path.endswith("/content"):
            item_id = unquote(parsed.path.split("/")[4])
            self._serve_drop_content(item_id)
            return
        if parsed.path == "/api/terminal/health":
            executable = shutil.which("powershell.exe") or shutil.which("powershell")
            python = find_python(self.server.context.registry.ecosystem_root)
            self._json({
                "ok": True,
                "cwd": str(self.server.context.registry.ecosystem_root),
                "available": bool(executable),
                "gitAvailable": bool(shutil.which("git.exe") or shutil.which("git")),
                "pythonAvailable": bool(python),
                "pythonExecutable": str(python) if python else "",
                "policy": {
                    "mode": "unrestricted",
                    "confirmationFor": [],
                    "allowedRoots": [],
                    "historyLimit": 50,
                    "maxOutputBytes": self.server.context.terminal_executions.max_output_bytes,
                    "maxConcurrentProcesses": self.server.context.terminal_executions.max_active,
                },
            })
            return
        if parsed.path.startswith("/api/terminal/processes/"):
            if not self._authorized_mutation():
                self._json({"error": "Sessão local inválida ou expirada."}, HTTPStatus.UNAUTHORIZED)
                return
            execution_id = unquote(parsed.path.removeprefix("/api/terminal/processes/")).strip("/")
            try:
                self._json(self.server.context.terminal_executions.snapshot(execution_id))
            except KeyError:
                self._json({"error": "Execução não encontrada."}, HTTPStatus.NOT_FOUND)
            return
        if parsed.path == "/api/terminal/completions":
            if not self._authorized_mutation():
                self._json({"error": "Sessão local inválida ou expirada."}, HTTPStatus.UNAUTHORIZED)
                return
            query = parse_qs(parsed.query)
            prefix = query.get("prefix", [""])[0]
            cwd = Path(query.get("cwd", [str(self.server.context.registry.ecosystem_root)])[0]).expanduser().resolve()
            if not cwd.is_dir():
                self._json({"items": []})
                return
            self._json({"items": self.server.context.terminal_executions.completions(prefix, cwd)})
            return
        if parsed.path == "/api/terminal/audit":
            if not self._authorized_mutation():
                self._json({"error": "Sessão local inválida ou expirada."}, HTTPStatus.UNAUTHORIZED)
                return
            limit = self._query_limit(parsed.query)
            self._json({"items": self.server.context.logs.tail("terminal", limit)})
            return
        if parsed.path.startswith("/api/logs/modules/"):
            if not self._authorized_mutation():
                self._json({"error": "Sessão local inválida ou expirada."}, HTTPStatus.UNAUTHORIZED)
                return
            module_id = unquote(parsed.path.removeprefix("/api/logs/modules/")).strip("/")
            limit = self._query_limit(parsed.query)
            self._json({"moduleId": module_id, "items": self.server.context.logs.tail(module_id, limit)})
            return
        if parsed.path.startswith("/api/"):
            self._json({"error": "Rota da API não encontrada."}, HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/module/"):
            self._serve_module_static(parsed.path)
            return
        if parsed.path.startswith("/design-system/"):
            self._serve_design_static(parsed.path)
            return
        self._serve_static(parsed.path)

    def do_OPTIONS(self) -> None:  # noqa: N802
        origin = self._cors_origin()
        if not origin:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range, X-File-Name, X-File-Kind, X-File-Last-Modified, X-Upload-Offset, X-Workspace-Token, Idempotency-Key")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        self._run_mutation(self._handle_POST)

    def _handle_POST(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/driver-remote/"):
            self._proxy_driver_request()
            return
        try:
            if path == "/api/shutdown":
                self._json({"ok": True, "message": "Workspace OS será encerrado."})
                def shutdown_later() -> None:
                    time.sleep(0.35)
                    self.server.shutdown()
                threading.Thread(target=shutdown_later, daemon=True).start()
                return
            if path == "/api/dropzone/uploads":
                payload = self._read_json()
                self._json(self.server.context.dropzone.begin_upload(
                    name=str(payload.get("name", "arquivo")),
                    mime=str(payload.get("type", "application/octet-stream")),
                    expected_size=int(payload.get("size", 0)),
                    last_modified=int(payload.get("lastModified", 0)),
                    folder_id=str(payload.get("folderId", "")),
                    relative_path=str(payload.get("relativePath", "")),
                ), HTTPStatus.CREATED)
                return
            upload_parts = [unquote(item) for item in path.strip("/").split("/")]
            if len(upload_parts) == 5 and upload_parts[:3] == ["api", "dropzone", "uploads"]:
                upload_id, action = upload_parts[3], upload_parts[4]
                if action == "chunk":
                    self._json(self._receive_upload_chunk(upload_id))
                    return
                if action == "complete":
                    self._json(self.server.context.dropzone.finish_upload(upload_id), HTTPStatus.CREATED)
                    return
            if path == "/api/dropzone/folders":
                payload = self._read_json()
                self._json(self.server.context.dropzone.begin_folder(
                    name=str(payload.get("name", "Pasta selecionada")),
                    expected_files=int(payload.get("fileCount", 0)),
                    expected_size=int(payload.get("size", 0)),
                ), HTTPStatus.CREATED)
                return
            folder_parts = [unquote(item) for item in path.strip("/").split("/")]
            if len(folder_parts) == 5 and folder_parts[:3] == ["api", "dropzone", "folders"] and folder_parts[4] == "complete":
                self._json(self.server.context.dropzone.finish_folder(folder_parts[3]))
                return
            if path == "/api/dropzone/files":
                self._json(self._receive_drop_item(), HTTPStatus.CREATED)
                return
            if path in {"/api/portable/inspect", "/api/portable/import"}:
                content = self._read_bytes(512 * 1024 * 1024)
                if path.endswith("/inspect"):
                    self._json(self.server.context.portable.inspect(content))
                else:
                    sections = set(parse_qs(urlparse(self.path).query).get("sections", [""])[0].split(","))
                    self._json(self.server.context.portable.restore(content, sections))
                return
            payload = self._read_json()
            if path == "/api/yasmin/command":
                texto = payload.get("texto")
                if not isinstance(texto, str) or not 0 < len(texto.strip()) <= 1000:
                    raise ValueError("Informe um comando de até 1000 caracteres")
                self._proxy_yasmin("POST", "/command", {"texto": texto.strip()})
                return
            if path == "/api/settings":
                self._json(self.server.context.settings.update(payload))
                self._trace("change", "Configurações atualizadas", detail=", ".join(payload.keys()), level="info")
                return
            if path == "/api/activity":
                self._json(self.server.context.activity.add(payload), HTTPStatus.CREATED)
                return
            if path == "/api/blackbox":
                self._json(self.server.context.blackbox.add(payload), HTTPStatus.CREATED)
                return
            if path == "/api/activity/read-all":
                self._json({"ok": True, "changed": self.server.context.activity.mark_all_read()})
                return
            if path == "/api/presets":
                self._json(self.server.context.presets.save(payload), HTTPStatus.CREATED)
                return
            if path == "/api/clipboard":
                self._json(self.server.context.clipboard.add(payload), HTTPStatus.CREATED)
                return
            if path.startswith("/api/clipboard/") and path.endswith("/pin"):
                item_id = unquote(path.split("/")[3])
                self._json(self.server.context.clipboard.pin(item_id, bool(payload.get("pinned", True))))
                return
            if path == "/api/integrations/bridge-agent":
                self._json(self.server.context.integrations.update_bridge_agent(payload))
                return
            if path == "/api/startup/enable":
                self._json(self.server.context.startup.enable())
                return
            if path == "/api/startup/disable":
                self._json(self.server.context.startup.disable())
                return
            if path == "/api/panel/open":
                webbrowser.open(self.server.context.registry.core_origin.url)
                self._json({"ok": True})
                return
            if path == "/api/terminal/command":
                result = self._run_terminal_command(payload)
                self._json(result, HTTPStatus.CONFLICT if result.get("confirmationRequired") else HTTPStatus.OK)
                return
            if path == "/api/terminal/processes":
                result = self._start_terminal_process(payload)
                status = HTTPStatus.CONFLICT if result.get("confirmationRequired") else HTTPStatus.CREATED
                self._json(result, status)
                return
            if path == "/api/modules/migrate":
                results = self.server.context.migrations.migrate_all(self.server.context.registry)
                self._json({"ok": all(item.get("ok") for item in results), "results": results})
                return
            if path == "/api/modules/reload":
                self._reload_registry()
                self._trace("change", "Manifestos recarregados", detail=f"{len(self.server.context.registry.modules)} módulos", level="info")
                self._json({"ok": True, "modules": len(self.server.context.registry.modules)})
                return
            if path == "/api/modules/install":
                result = self.server.context.git.install(payload)
                self._reload_registry()
                self._json(result, HTTPStatus.CREATED)
                return
            if path.startswith("/api/module-data/"):
                module_id = unquote(path.removeprefix("/api/module-data/")).strip("/")
                self._json(self.server.context.module_data.save(module_id, payload), HTTPStatus.CREATED)
                return
            parts = [unquote(item) for item in path.strip("/").split("/")]
            if len(parts) == 4 and parts[:2] == ["api", "modules"]:
                module_id, action = parts[2], parts[3]
                settings = self.server.context.settings.load()
                if action in {"enable", "disable"}:
                    disabled = list(settings.get("disabled_modules", []))
                    if action == "disable" and module_id not in disabled:
                        disabled.append(module_id)
                        self.server.context.processes.stop(module_id)
                    if action == "enable":
                        disabled = [item for item in disabled if item != module_id]
                    self._json(self.server.context.settings.update({"disabled_modules": disabled}))
                    return
                if action == "git-status":
                    self._json(self.server.context.git.status(self.server.context.registry.get(module_id), fetch=bool(payload.get("fetch"))))
                    return
                if action == "git-update":
                    self._json(self._update_module_with_rollback(module_id, settings))
                    return
                if action == "restart":
                    if module_id == "drive2" and not settings["module_configs"]["drive2"].get("run_local", True):
                        raise ValueError("O InkDriver está configurado para usar um servidor remoto.")
                    self.server.context.processes.stop(module_id)
                    self._json(self.server.context.processes.start(
                        module_id, effective_module_urls(settings).get(module_id), settings["module_configs"].get(module_id),
                    ))
                    return
                if action == "start":
                    if module_id in settings.get("disabled_modules", []):
                        raise ValueError("Ative o módulo antes de iniciá-lo.")
                    if module_id == "drive2" and not settings["module_configs"]["drive2"].get("run_local", True):
                        raise ValueError("O InkDriver está configurado para usar um servidor remoto.")
                    result = self.server.context.processes.start(
                        module_id,
                        effective_module_urls(settings).get(module_id),
                        settings["module_configs"].get(module_id),
                    )
                    self._json(result)
                    return
                if action == "stop":
                    self._json(self.server.context.processes.stop(module_id))
                    return
            self._json({"error": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)
        except KeyError as exc:
            self._json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        except (ValueError, OSError, RuntimeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def do_DELETE(self) -> None:  # noqa: N802
        self._run_mutation(self._handle_DELETE)

    def _handle_DELETE(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/driver-remote/"):
            self._proxy_driver_request()
            return
        upload_parts = [unquote(item) for item in path.strip("/").split("/")]
        if len(upload_parts) == 4 and upload_parts[:3] == ["api", "dropzone", "uploads"]:
            removed = self.server.context.dropzone.cancel_upload(upload_parts[3])
            self._json({"ok": True, "removed": removed})
            return
        if path == "/api/activity":
            self._json({"ok": True, "removed": self.server.context.activity.clear()})
            return
        if path == "/api/blackbox":
            self._json({"ok": True, "removed": self.server.context.blackbox.clear()})
            return
        if path.startswith("/api/activity/"):
            item_id = unquote(path.removeprefix("/api/activity/")).strip("/")
            if not self.server.context.activity.remove(item_id):
                self._json({"error": "Atividade não encontrada."}, HTTPStatus.NOT_FOUND)
                return
            self._json({"ok": True, "id": item_id})
            return
        if path.startswith("/api/presets/"):
            preset_id = unquote(path.removeprefix("/api/presets/")).strip("/")
            if not self.server.context.presets.remove(preset_id):
                self._json({"error": "Preset não encontrado."}, HTTPStatus.NOT_FOUND)
                return
            self._json({"ok": True, "id": preset_id})
            return
        if path.startswith("/api/clipboard/"):
            item_id = unquote(path.removeprefix("/api/clipboard/")).strip("/")
            if not self.server.context.clipboard.remove(item_id):
                self._json({"error": "Item não encontrado."}, HTTPStatus.NOT_FOUND)
                return
            self._json({"ok": True, "id": item_id})
            return
        if path.startswith("/api/terminal/processes/"):
            execution_id = unquote(path.removeprefix("/api/terminal/processes/")).strip("/")
            try:
                self._json(self.server.context.terminal_executions.cancel(execution_id))
            except KeyError:
                self._json({"error": "Execução não encontrada."}, HTTPStatus.NOT_FOUND)
            return
        prefix = "/api/dropzone/files/"
        if not path.startswith(prefix) or path.endswith("/content"):
            self._json({"error": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)
            return
        item_id = unquote(path[len(prefix):]).strip("/")
        if not item_id:
            self._json({"error": "Item inválido."}, HTTPStatus.BAD_REQUEST)
            return
        removed = self.server.context.dropzone.remove(item_id)
        if not removed:
            self._json({"error": "Item não encontrado."}, HTTPStatus.NOT_FOUND)
            return
        self._json({"ok": True, "id": item_id})

    def do_PATCH(self) -> None:  # noqa: N802
        self._run_mutation(self._proxy_driver_method)

    def do_PUT(self) -> None:  # noqa: N802
        self._run_mutation(self._proxy_driver_method)

    def _proxy_driver_method(self) -> None:
        if not urlparse(self.path).path.startswith("/api/driver-remote/"):
            self._json({"error": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)
            return
        self._proxy_driver_request()

    def _proxy_driver_request(self) -> None:
        """Keep the Workspace shell local while the InkDriver API runs remotely."""
        settings = self.server.context.settings.load()
        driver = settings.get("module_configs", {}).get("drive2", {})
        remote_url = str(settings.get("module_urls", {}).get("drive2", "")).rstrip("/")
        if driver.get("run_local", True) or not remote_url:
            self._json({"error": "O InkDriver remoto não está configurado."}, HTTPStatus.BAD_REQUEST)
            return

        parsed_remote = urlparse(remote_url)
        if parsed_remote.scheme not in {"http", "https"} or not parsed_remote.hostname:
            self._json({"error": "Endereço remoto do InkDriver inválido."}, HTTPStatus.BAD_REQUEST)
            return

        parsed_request = urlparse(self.path)
        upstream_path = unquote(parsed_request.path.removeprefix("/api/driver-remote")) or "/"
        base_path = parsed_remote.path.rstrip("/")
        target_path = f"{base_path}{upstream_path}"
        if parsed_request.query:
            target_path += f"?{parsed_request.query}"

        port = parsed_remote.port or (443 if parsed_remote.scheme == "https" else 80)
        connection_type = http.client.HTTPSConnection if parsed_remote.scheme == "https" else http.client.HTTPConnection
        max_upload = int(driver.get("max_upload_mb", 1024)) * 1024 * 1024 + 2 * 1024 * 1024
        length = self._content_length(maximum=max_upload)
        connection = connection_type(parsed_remote.hostname, port, timeout=120)

        body = self.rfile.read(length) if length else None
        forwarded: dict[str, str] = {
            "Host": parsed_remote.netloc,
            "Connection": "close",
        }
        for name in ("Accept", "Content-Type", "Cookie", "Range", "If-None-Match", "If-Modified-Since", "User-Agent"):
            value = self.headers.get(name)
            if value:
                forwarded[name] = value
        if length:
            forwarded["Content-Length"] = str(length)

        response_started = False
        try:
            connection.request(self.command, target_path, body=body, headers=forwarded)
            response = connection.getresponse()
            self.send_response(response.status, response.reason)
            response_started = True
            has_length = False
            excluded = {"connection", "transfer-encoding", "server", "date"}
            for name, value in response.getheaders():
                if name.lower() in excluded:
                    continue
                if name.lower() == "content-length":
                    has_length = True
                self.send_header(name, value)
            if not has_length:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (OSError, http.client.HTTPException) as exc:
            if not response_started and not self.wfile.closed:
                self._json({"error": f"InkDriver remoto indisponível: {exc}"}, HTTPStatus.BAD_GATEWAY)
            else:
                self.close_connection = True
        finally:
            connection.close()

    def _trusted_request(self) -> bool:
        try:
            host = urlparse(f"//{self.headers.get('Host', '')}").hostname or ""
        except ValueError:
            return False
        if host not in {"127.0.0.1", "localhost", "::1"}:
            return False
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        return parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost", "::1"}

    def _proxy_yasmin(self, metodo: str, caminho: str, payload: dict | None = None) -> None:
        conexao = http.client.HTTPConnection("127.0.0.1", YASMIN_BRIDGE_PORT, timeout=20)
        try:
            corpo = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
            conexao.request(metodo, caminho, body=corpo,
                            headers={"Content-Type": "application/json",
                                     "X-Yasmin-Bridge": "workspace-os"})
            resposta = conexao.getresponse()
            if resposta.length is not None and resposta.length > 64 * 1024:
                raise ValueError("Resposta da Yasmin excedeu o limite")
            dados = json.loads(resposta.read(64 * 1024 + 1).decode("utf-8"))
            if not isinstance(dados, dict):
                raise ValueError("Resposta inválida da Yasmin")
            self._json(dados, HTTPStatus(resposta.status))
        except (OSError, ValueError, json.JSONDecodeError):
            self._json({"ok": False, "erro": "Yasmin ainda não está disponível."},
                       HTTPStatus.SERVICE_UNAVAILABLE)
        finally:
            conexao.close()

    def _authorized_mutation(self) -> bool:
        if not self._trusted_request():
            return False
        token = self.headers.get("X-Workspace-Token", "")
        if not token:
            cookies = self.headers.get("Cookie", "")
            for item in cookies.split(";"):
                name, _, value = item.strip().partition("=")
                if name == "workspace_session":
                    token = value
                    break
        return self.server.context.auth.verify(token)

    def _run_mutation(self, callback: Any) -> None:
        if not self._trusted_request():
            self._json({"error": "Origem não autorizada."}, HTTPStatus.FORBIDDEN)
            return
        if not self._authorized_mutation():
            self._json({"error": "Sessão local inválida ou expirada.", "code": "SESSION_REQUIRED"}, HTTPStatus.UNAUTHORIZED)
            return
        path = urlparse(self.path).path
        if path in {"/api/modules/reload", "/api/modules/install"} or path.endswith("/git-update"):
            operation = "MODULE_REGISTRY_MUTATION"
        else:
            operation = f"{self.command} {path}"
        accepted, message = self.server.context.operation_gate.acquire(operation, self.headers.get("Idempotency-Key", ""))
        if not accepted:
            self._json({"error": message, "code": "OPERATION_IN_PROGRESS"}, HTTPStatus.CONFLICT)
            return
        try:
            callback()
        except KeyError as exc:
            self._json({"error": str(exc)}, HTTPStatus.NOT_FOUND)
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # Last-resort request isolation; details stay in local diagnostics.
            self._trace(
                "error", f"Falha interna em {operation}",
                detail=f"{type(exc).__name__}: {exc}", level="error",
            )
            if not self._response_started:
                self._json(
                    {"error": "O Workspace não conseguiu concluir esta operação. Consulte Diagnóstico > Caixa-preta."},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            else:
                self.close_connection = True
        finally:
            self.server.context.operation_gate.release(operation)

    def _cors_origin(self) -> str | None:
        origin = self.headers.get("Origin")
        if not origin:
            return None
        parsed = urlparse(origin)
        if parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
            return origin
        return None

    def _send_cors(self) -> None:
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Credentials", "true")

    def _read_json(self) -> dict[str, Any]:
        length = self._content_length(maximum=64 * 1024)
        if not length:
            self._trace("request", f"{self.command} {urlparse(self.path).path}", level="info")
            return {}
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("O corpo da solicitação precisa ser um objeto JSON.")
        if urlparse(self.path).path != "/api/blackbox":
            self._trace("request", f"{self.command} {urlparse(self.path).path}", level="info")
        return payload

    def _receive_drop_item(self) -> dict[str, Any]:
        length = self._content_length()
        name = unquote(self.headers.get("X-File-Name", "arquivo"))
        kind = self.headers.get("X-File-Kind", "file")
        last_modified = int(self.headers.get("X-File-Last-Modified", "0") or 0)
        if kind == "folder":
            return self.server.context.dropzone.begin_folder(name=name, expected_files=0, expected_size=0)
        upload = self.server.context.dropzone.begin_upload(
            name=name, mime=self.headers.get("Content-Type", "application/octet-stream"),
            expected_size=length, last_modified=last_modified,
        )
        if length:
            self.server.context.dropzone.append_upload(upload["uploadId"], 0, self.rfile, length)
        return self.server.context.dropzone.finish_upload(upload["uploadId"])

    def _receive_upload_chunk(self, upload_id: str) -> dict[str, Any]:
        length = self._content_length(maximum=64 * 1024 * 1024)
        offset = int(self.headers.get("X-Upload-Offset", "0") or 0)
        return self.server.context.dropzone.append_upload(upload_id, offset, self.rfile, length)

    def _serve_drop_content(self, item_id: str) -> None:
        try:
            record, path = self.server.context.dropzone.get(item_id)
        except KeyError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if path is None:
            self.send_error(HTTPStatus.BAD_REQUEST)
            return
        self._trace("file", f"Arquivo acessado: {record.get('name', 'arquivo')}", path=str(path), level="info")
        self._serve_file_path(record, path)

    def _serve_file_path(self, record: dict[str, Any], path: Path) -> None:
        size = path.stat().st_size
        start, end = 0, max(0, size - 1)
        status = HTTPStatus.OK
        requested_range = self.headers.get("Range", "")
        if requested_range.startswith("bytes=") and size:
            try:
                left, right = requested_range.removeprefix("bytes=").split("-", 1)
                start = int(left) if left else 0
                end = min(size - 1, int(right)) if right else size - 1
                if start < 0 or start > end or start >= size:
                    raise ValueError
                status = HTTPStatus.PARTIAL_CONTENT
            except ValueError:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        length = 0 if not size else end - start + 1
        self.send_response(status)
        mime = str(record.get("type") or "application/octet-stream").strip()
        if "\r" in mime or "\n" in mime or "/" not in mime or not mime.isascii():
            mime = "application/octet-stream"
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-File-Name", quote(str(record.get("name", "arquivo")), safe="._-()[]"))
        self.send_header("Access-Control-Expose-Headers", "X-File-Name, Content-Type, Content-Length, Content-Range, Accept-Ranges")
        self._send_cors()
        self.end_headers()
        if not length:
            return
        with path.open("rb") as source:
            source.seek(start)
            remaining = length
            while remaining:
                chunk = source.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _diagnostics(self) -> dict[str, Any]:
        settings = self.server.context.settings.load()
        modules = self.server.context.registry.serialize(effective_module_urls(settings))
        drop_items = self.server.context.dropzone.history()
        activities = self.server.context.activity.list(limit=250)
        disk = shutil.disk_usage(self.server.context.settings.data_dir.parent)
        audit = module_audit(self.server.context.registry, self.server.context.processes, effective_module_urls(settings))
        diagnostic_modules = []
        audit_by_id = {str(item.get("id")): item for item in audit.get("modules", [])}
        for module in modules:
            issues = audit_by_id.get(str(module["id"]), {}).get("issues", [])
            first = issues[0] if issues else {}
            if not first and module["kind"] == "web-service" and not module["reachable"]:
                first = {
                    "code": "SERVICE_UNREACHABLE",
                    "message": "O serviço não respondeu ao teste local.",
                    "probableCause": "O processo está parado, ainda iniciando ou a porta configurada está ocupada.",
                    "recoveryAction": "Use Reiniciar; se persistir, confira o log estruturado e a porta do módulo.",
                }
            diagnostic_modules.append({
                "id": module["id"], "name": module["name"], "installed": module["installed"],
                "reachable": module["reachable"], "managedState": self.server.context.processes.managed_state(str(module["id"])),
                "probableCause": first.get("probableCause", "Nenhuma falha detectada."),
                "recoveryAction": first.get("recoveryAction", "Nenhuma ação necessária."),
                "code": first.get("code", "OK"),
            })
        findings = []
        if disk.free < 1024 * 1024 * 1024:
            findings.append({"code": "LOW_DISK", "level": "warning", "title": "Pouco espaço livre", "probableCause": "A unidade de dados possui menos de 1 GiB disponível.", "recoveryAction": "Limpe arquivos temporários ou mova a pasta de dados."})
        if self.server.context.registry.discovery_errors:
            findings.append({"code": "INVALID_MANIFEST", "level": "error", "title": "Manifesto isolado", "probableCause": "Um módulo possui ink-module.json inválido ou pede uma permissão não confiável.", "recoveryAction": "Corrija o manifesto indicado; os demais módulos continuam disponíveis."})
        return {
            "version": __version__,
            "runtime": f"Python {platform.python_version()}",
            "platform": platform.platform(),
            "processId": os.getpid(),
            "dataDirectory": str(self.server.context.settings.data_dir),
            "ecosystemRoot": str(self.server.context.registry.ecosystem_root),
            "startup": self.server.context.startup.status(),
            "terminal": {
                "available": bool(shutil.which("powershell.exe") or shutil.which("powershell")),
                "gitAvailable": bool(shutil.which("git.exe") or shutil.which("git")),
                "pythonAvailable": bool(find_python(self.server.context.registry.ecosystem_root)),
            },
            "storage": {
                "diskTotal": disk.total,
                "diskFree": disk.free,
                "dropzoneItems": len(drop_items),
                "dropzoneBytes": sum(int(item.get("size", 0) or 0) for item in drop_items),
                "moduleSnapshots": self.server.context.module_data.list(),
            },
            "audit": audit,
            "findings": findings,
            "security": {"sessionExpiresAt": self.server.context.auth.expires_at, "mutationsRequireToken": True, "concurrentMutationGuard": True},
            "logs": self.server.context.logs.summary(),
            "activity": {
                "count": len(activities),
                "unread": sum(1 for item in activities if not item.get("read")),
                "recentErrors": [item for item in activities if item.get("level") == "error"][:8],
            },
            "modules": diagnostic_modules,
        }

    def _update_module_with_rollback(self, module_id: str, settings: dict[str, Any]) -> dict[str, Any]:
        module = self.server.context.registry.get(module_id)
        revision = self.server.context.git.revision(module)
        was_running = self.server.context.processes.managed_state(module_id) == "running"
        if was_running:
            self.server.context.processes.stop(module_id)
        self.server.context.logs.write(module_id, "update.started", revision=revision)
        try:
            result = self.server.context.git.update(module)
            self._reload_registry()
            updated = self.server.context.registry.get(module_id)
            if updated.entry_file and updated.project_path and not (updated.project_path / updated.entry_file).is_file():
                raise RuntimeError(f"A nova versão não contém {updated.entry_file}.")
            if updated.kind == "web-service" and (was_running or updated.auto_start):
                self.server.context.processes.start(
                    module_id, effective_module_urls(settings).get(module_id), settings.get("module_configs", {}).get(module_id),
                )
                health_url = effective_module_urls(settings).get(module_id) or updated.health_url or updated.url
                deadline = time.monotonic() + 8
                while health_url and time.monotonic() < deadline and not ModuleRegistry.is_reachable(health_url, timeout=0.3):
                    time.sleep(0.2)
                if health_url and not ModuleRegistry.is_reachable(health_url, timeout=0.3):
                    raise RuntimeError("A nova versão iniciou, mas não passou no teste de saúde.")
            migration = self.server.context.migrations.migrate(updated)
            self.server.context.logs.write(module_id, "update.completed", migration=migration)
            return {**result, "rollback": False, "migration": migration}
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            try:
                current = self.server.context.registry.modules.get(module_id, module)
                self.server.context.processes.stop(module_id)
                rollback = self.server.context.git.rollback(current, revision)
                self._reload_registry()
                restored = self.server.context.registry.get(module_id)
                if was_running:
                    self.server.context.processes.start(
                        module_id, effective_module_urls(settings).get(module_id), settings.get("module_configs", {}).get(module_id),
                    )
                self.server.context.logs.write(module_id, "update.rolled_back", level="error", error=str(exc), revision=revision)
                return {"ok": False, "message": f"Atualização revertida automaticamente: {exc}", "rollback": True, "rollbackResult": rollback, "version": restored.version}
            except (OSError, ValueError, RuntimeError, KeyError) as rollback_error:
                self.server.context.logs.write(module_id, "update.rollback_failed", level="error", error=str(rollback_error), originalError=str(exc))
                raise RuntimeError(f"A atualização falhou ({exc}) e o rollback também falhou ({rollback_error}).") from rollback_error

    def _reload_registry(self) -> None:
        context = self.server.context
        registry = ModuleRegistry(context.workspace_root / "config/modules.json", context.registry.ecosystem_root)
        context.registry = registry
        context.processes.registry = registry
        for result in context.migrations.migrate_all(registry):
            if result.get("changed") or not result.get("ok"):
                context.logs.write(str(result.get("moduleId", "core")), "migration.reload", level="info" if result.get("ok") else "error", result=result)

    def _read_bytes(self, maximum: int) -> bytes:
        length = self._content_length(maximum=maximum)
        if length <= 0:
            raise ValueError("Tamanho de arquivo inválido.")
        return self.rfile.read(length)

    def _content_length(self, *, maximum: int | None = None) -> int:
        raw = self.headers.get("Content-Length", "0") or "0"
        try:
            length = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("Content-Length inválido.") from exc
        if length < 0:
            raise ValueError("Content-Length não pode ser negativo.")
        if maximum is not None and length > maximum:
            raise ValueError(f"A solicitação excede o limite de {maximum} bytes.")
        return length

    @staticmethod
    def _query_limit(query: str, *, default: int = 100, maximum: int = 500) -> int:
        raw = parse_qs(query).get("limit", [str(default)])[0]
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return default
        return max(1, min(value, maximum))

    def _authorize_terminal_request(self, payload: dict[str, Any]) -> tuple[str, Path, Any] | dict[str, Any]:
        command = payload.get("command")
        cwd_value = payload.get("cwd") or str(self.server.context.registry.ecosystem_root)
        if not isinstance(command, str) or not command.strip():
            raise ValueError("Digite um comando.")
        if len(command) > 16_384 or "\x00" in command:
            raise ValueError("O comando excede o limite permitido.")
        cwd = Path(str(cwd_value)).expanduser().resolve()
        if not cwd.is_dir():
            raise ValueError("A pasta atual não existe.")

        stripped = command.strip()
        decision = self.server.context.terminal_policy.classify(command)
        return stripped, cwd, decision

    def _terminal_invocation(self, stripped: str, cwd: Path) -> tuple[list[str], dict[str, str], str | None] | dict[str, Any]:
        python_match = PYTHON_COMMAND.match(stripped)
        pip_match = PIP_COMMAND.match(stripped)
        python = find_python(cwd) if python_match or pip_match else None
        if (python_match or pip_match) and not python:
            return {
                "ok": False, "exitCode": 127, "cwd": str(cwd), "stdout": [],
                "stderr": ["Python não foi encontrado nesta pasta nem nas instalações do computador."], "durationMs": 0,
            }
        if python_match:
            remainder = stripped[python_match.end():]
            stripped = f"& {powershell_quote(str(python))}{remainder or ' --version'}"
        elif pip_match:
            remainder = stripped[pip_match.end():]
            stripped = f"& {powershell_quote(str(python))} -m pip{remainder or ' --version'}"

        legacy_windows_command = uses_legacy_windows_encoding(stripped)
        if legacy_windows_command:
            executable = shutil.which("cmd.exe")
            args = [executable, "/d", "/s", "/c", stripped] if executable else []
        else:
            executable = shutil.which("powershell.exe") or shutil.which("powershell")
            prefix = "$ProgressPreference='SilentlyContinue'; $utf8=[Text.UTF8Encoding]::new($false); [Console]::InputEncoding=$utf8; [Console]::OutputEncoding=$utf8; $OutputEncoding=$utf8; "
            script = prefix + stripped
            import base64
            encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
            args = [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-OutputFormat", "Text", "-EncodedCommand", encoded] if executable else []
        if not args:
            raise RuntimeError("O Terminal não está disponível neste computador.")

        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"
        project_python = find_python(cwd)
        if project_python:
            environment["PATH"] = f"{project_python.parent}{os.pathsep}{environment.get('PATH', '')}"
        repository = next((candidate for candidate in (cwd, *cwd.parents) if (candidate / ".git").exists()), None)
        if repository is not None:
            count = int(environment.get("GIT_CONFIG_COUNT", "0") or 0)
            environment["GIT_CONFIG_COUNT"] = str(count + 1)
            environment[f"GIT_CONFIG_KEY_{count}"] = "safe.directory"
            environment[f"GIT_CONFIG_VALUE_{count}"] = str(repository)
        return args, environment, "mbcs" if legacy_windows_command else None

    def _start_terminal_process(self, payload: dict[str, Any]) -> dict[str, Any]:
        authorized = self._authorize_terminal_request(payload)
        if isinstance(authorized, dict):
            return authorized
        stripped, cwd, decision = authorized
        lowered = stripped.lower()
        if lowered in {"pwd", "cd"} or lowered.startswith("cd ") or lowered.startswith("cd\t") or PYTHON_PRINT_EXPRESSION.match(stripped):
            result = self._run_terminal_command(payload, authorized=authorized)
            return {**result, "status": "completed", "executionId": None, "pid": None, "resources": {}}
        invocation = self._terminal_invocation(stripped, cwd)
        if isinstance(invocation, dict):
            return {**invocation, "permission": decision.permission, "risk": decision.risk, "status": "completed", "executionId": None, "pid": None, "resources": {}}
        args, environment, output_encoding = invocation
        return self.server.context.terminal_executions.start(
            args=args,
            cwd=cwd,
            environment=environment,
            command=stripped,
            session_id=str(payload.get("sessionId", "default")),
            permission=decision.permission,
            risk=decision.risk,
            output_encoding=output_encoding,
        )

    def _run_terminal_command(
        self, payload: dict[str, Any], *, authorized: tuple[str, Path, Any] | None = None,
    ) -> dict[str, Any]:
        authorized_result = authorized or self._authorize_terminal_request(payload)
        if isinstance(authorized_result, dict):
            return authorized_result
        stripped, cwd, decision = authorized_result

        requested_command = stripped
        lowered = stripped.lower()
        if lowered in {"pwd", "cd"}:
            return {"ok": True, "exitCode": 0, "cwd": str(cwd), "stdout": [str(cwd)], "stderr": [], "durationMs": 0, "permission": decision.permission, "risk": decision.risk}
        if lowered.startswith("cd ") or lowered.startswith("cd\t"):
            target_text = stripped[2:].strip().strip('"').strip("'")
            target = Path(os.path.expandvars(target_text)).expanduser()
            if not target.is_absolute():
                target = cwd / target
            target = target.resolve()
            if not target.is_dir():
                return {"ok": False, "exitCode": 1, "cwd": str(cwd), "stdout": [], "stderr": [f"Pasta não encontrada: {target}"], "durationMs": 0, "permission": decision.permission, "risk": decision.risk}
            return {"ok": True, "exitCode": 0, "cwd": str(target), "stdout": [str(target)], "stderr": [], "durationMs": 0, "permission": decision.permission, "risk": decision.risk}

        if PYTHON_PRINT_EXPRESSION.match(stripped):
            return {
                "ok": False, "exitCode": 2, "cwd": str(cwd), "stdout": [],
                "stderr": [
                    "O Ink Terminal executa comandos do PowerShell, não expressões Python diretamente.",
                    "Use: python -c \"print('ooi')\"",
                ],
                "durationMs": 0,
                "permission": decision.permission,
                "risk": decision.risk,
            }

        invocation = self._terminal_invocation(stripped, cwd)
        if isinstance(invocation, dict):
            return {**invocation, "permission": decision.permission, "risk": decision.risk}
        args, environment, output_encoding = invocation
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                args,
                cwd=cwd,
                env=environment,
                capture_output=True,
                timeout=45,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as exc:
            stdout = decode_terminal_output(exc.stdout, output_encoding)
            stderr = decode_terminal_output(exc.stderr, output_encoding)
            return {
                "ok": False, "exitCode": 124, "cwd": str(cwd),
                "stdout": stdout.splitlines()[-1000:],
                "stderr": [*stderr.splitlines()[-999:], "Tempo limite de 45 segundos excedido."],
                "durationMs": 45_000,
                "permission": decision.permission,
                "risk": decision.risk,
            }
        elapsed = round((time.perf_counter() - started) * 1000)
        stdout = decode_terminal_output(completed.stdout, output_encoding)
        stderr = decode_terminal_output(completed.stderr, output_encoding)
        result = {
            "ok": completed.returncode == 0,
            "exitCode": completed.returncode,
            "cwd": str(cwd),
            "stdout": stdout.splitlines()[-2000:],
            "stderr": stderr.splitlines()[-2000:],
            "durationMs": elapsed,
            "permission": decision.permission,
            "risk": decision.risk,
        }
        if not result["ok"]:
            self._trace("error", f"Falha no Terminal: {requested_command.split(maxsplit=1)[0]}", detail="\n".join(result["stderr"][-6:]), path=str(cwd))
        return result

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        candidate = (self.server.context.web_root / relative).resolve()
        try:
            candidate.relative_to(self.server.context.web_root.resolve())
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            candidate = self.server.context.web_root / "index.html"
        content = candidate.read_bytes()
        if candidate.suffix.lower() in {".html", ".js", ".css"}:
            content = content.replace(b"http://127.0.0.1:8790", self.server.context.registry.core_origin.url.encode("utf-8"))
        mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if mime == "text/html" and b"theme-preload.js" not in content:
            content = content.replace(
                b"<head>",
                b'<head><script src="/core/theme-preload.js"></script>',
                1,
            )
        if mime.startswith("text/") or mime in {"application/javascript", "application/json"}:
            mime += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; frame-src 'self' http://127.0.0.1:* http://localhost:*; img-src 'self' data:; connect-src 'self' http://127.0.0.1:* http://localhost:*")
        self._send_cors()
        self.end_headers()
        self.wfile.write(content)

    def _serve_module_static(self, request_path: str) -> None:
        parts = request_path.lstrip("/").split("/", 2)
        if len(parts) != 3:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        _, module_id, relative = parts
        try:
            module = self.server.context.registry.get(module_id)
        except KeyError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if module_id in self.server.context.settings.load().get("disabled_modules", []):
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "Módulo desativado")
            return
        serves_driver_shell = module.id == "drive2" and module.kind == "web-service" and relative.startswith("web/")
        # A web-service can expose a tiny Workspace-owned shell in workspace/.
        # Its actual application keeps running on its own origin inside an iframe,
        # which prevents its CSS and scripts from affecting the Core components.
        serves_workspace_shell = (
            module.kind == "web-service"
            and bool(module.entry_file)
            and module.entry_file.startswith("workspace/")
            and relative.startswith("workspace/")
        )
        if (module.kind != "static-web" and not serves_driver_shell and not serves_workspace_shell) or not module.project_path:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        candidate = (module.project_path / unquote(relative)).resolve()
        try:
            candidate.relative_to(module.project_path)
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = candidate.read_bytes()
        if candidate.suffix.lower() in {".html", ".js", ".css"}:
            content = content.replace(b"http://127.0.0.1:8790", self.server.context.registry.core_origin.url.encode("utf-8"))
        if candidate.suffix.lower() == ".html":
            self._trace("file", f"Interface aberta: {module.name}", path=str(candidate), module_id=module.id, level="info")
            if serves_driver_shell:
                content = content.replace(b'="/static/', b'="/module/drive2/web/')
        mime = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if mime == "text/html" and b"theme-preload.js" not in content:
            content = content.replace(
                b"<head>",
                b'<head><script src="/core/theme-preload.js"></script>',
                1,
            )
        if mime.startswith("text/") or mime in {"application/javascript", "application/json"}:
            mime += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self._send_cors()
        self.end_headers()
        self.wfile.write(content)

    def _serve_design_static(self, request_path: str) -> None:
        relative = unquote(request_path.removeprefix("/design-system/")).strip("/")
        candidate = (self.server.context.design_root / relative).resolve()
        try:
            candidate.relative_to(self.server.context.design_root.resolve())
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if relative == "workspace-ui.css" and not candidate.is_file():
            candidate = self.server.context.web_root / "workspace-ui-fallback.css"
        if not candidate.is_file() or candidate.suffix.lower() != ".css":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/css; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self._send_cors()
        self.end_headers()
        self.wfile.write(content)

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        if int(status) >= 400 and urlparse(self.path).path != "/api/blackbox":
            detail = payload.get("error", "") if isinstance(payload, dict) else ""
            self._trace("error", f"{self.command} {urlparse(self.path).path} retornou {int(status)}", detail=str(detail))
        content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if urlparse(self.path).path == "/api/session" and self.server.context.auth:
            self.send_header("Set-Cookie", f"workspace_session={self.server.context.auth.token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={self.server.context.auth.ttl_seconds}")
        self._send_cors()
        self.end_headers()
        self.wfile.write(content)

    def _trace(self, kind: str, title: str, *, detail: str = "", path: str = "", module_id: str = "", level: str = "error") -> None:
        try:
            self.server.context.blackbox.add({"kind": kind, "title": title, "detail": detail, "path": path, "moduleId": module_id, "level": level})
        except (OSError, ValueError):
            pass
        try:
            self.server.context.logs.write(module_id or "core", kind, level=level, title=title, detail=detail, path=path)
        except (OSError, ValueError):
            pass

    def _binary(self, content: bytes, mime: str, filename: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "no-store")
        self._send_cors()
        self.end_headers()
        self.wfile.write(content)


def create_context(workspace_root: Path, data_dir: Path | None = None) -> AppContext:
    workspace_root = workspace_root.resolve()
    ecosystem_root = workspace_root.parent
    settings = SettingsStore(data_dir)
    registry = ModuleRegistry(workspace_root / "config/modules.json", ecosystem_root)
    logs = StructuredModuleLogs(settings.data_dir)
    processes = ProcessManager(registry, settings.data_dir, workspace_root, logs)
    startup = WindowsStartup(workspace_root / "launcher.py")
    module_data = ModuleDataStore(settings.data_dir)
    blackbox = BlackBoxStore(settings.data_dir)
    activity = ActivityStore(settings.data_dir)
    presets = PresetStore(settings.data_dir)
    clipboard = ClipboardStore(settings.data_dir)
    dropzone = DropzoneStore(settings.data_dir)
    context = AppContext(
        workspace_root=workspace_root,
        web_root=workspace_root / "web",
        design_root=ecosystem_root / "workspace-design-system" / "src",
        registry=registry,
        settings=settings,
        processes=processes,
        startup=startup,
        dropzone=dropzone,
        activity=activity,
        presets=presets,
        clipboard=clipboard,
        integrations=IntegrationProfiles(),
        module_data=module_data,
        portable=PortableArchive(settings, activity, presets, clipboard, dropzone, module_data, ecosystem_root),
        git=GitProjects(ecosystem_root),
        blackbox=blackbox,
        auth=SessionAuth(),
        operation_gate=OperationGate(),
        terminal_policy=TerminalPolicy(),
        logs=logs,
        migrations=ModuleMigrationRunner(module_data, settings.data_dir),
    )
    for result in context.migrations.migrate_all(registry):
        if result.get("changed") or not result.get("ok"):
            logs.write(str(result.get("moduleId", "core")), "migration.startup", level="info" if result.get("ok") else "error", result=result)
    return context


def start_background_modules(context: AppContext) -> list[dict[str, object]]:
    settings = context.settings.load()
    module_ids = list(settings["auto_start_modules"])
    if not settings["module_configs"]["drive2"].get("run_local", True):
        module_ids = [module_id for module_id in module_ids if module_id != "drive2"]
    results = context.processes.start_configured(
        module_ids, effective_module_urls(settings), settings["module_configs"]
    )
    for result in results:
        context.logs.write(
            str(result.get("module", "core")),
            "startup.module",
            level="info" if result.get("ok") else "warning",
            ok=result.get("ok"),
            message=result.get("message"),
        )
    return results


def open_panel_later(delay: float = 0.8, url: str | None = None) -> None:
    def open_panel() -> None:
        time.sleep(delay)
        webbrowser.open(url or CoreOrigin().url)

    threading.Thread(target=open_panel, daemon=True).start()
