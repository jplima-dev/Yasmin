from __future__ import annotations

import json
import os
import queue
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, TextIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from . import __version__
from .module_sdk import validate_modules
from .origin import CoreOrigin
from .registry import ModuleDefinition, ModuleRegistry
from .settings import SettingsStore, effective_module_urls


@dataclass(frozen=True)
class DoctorCheck:
    level: str
    title: str
    detail: str = ""
    code: str = ""


@dataclass(frozen=True)
class DoctorReport:
    checks: tuple[DoctorCheck, ...]

    @property
    def counts(self) -> dict[str, int]:
        return {
            level: sum(check.level == level for check in self.checks)
            for level in ("ok", "warning", "error")
        }

    @property
    def exit_code(self) -> int:
        return 1 if self.counts["error"] else 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": "Workspace Doctor",
            "version": __version__,
            "checks": [asdict(check) for check in self.checks],
            "result": self.counts,
            "ok": self.exit_code == 0,
        }

    def render(self, *, ascii_only: bool = False) -> str:
        symbols = {
            "ok": "[OK]" if ascii_only else "✓",
            "warning": "[AVISO]" if ascii_only else "⚠",
            "error": "[ERRO]" if ascii_only else "✗",
        }
        lines = ["Workspace Doctor", ""]
        for check in self.checks:
            line = f"{symbols[check.level]} {check.title}"
            if check.detail:
                line += f" — {check.detail}"
            lines.append(line)
        counts = self.counts
        lines.extend([
            "",
            "Resultado:",
            f"{counts['ok']} OK",
            f"{counts['warning']} avisos",
            f"{counts['error']} erros",
        ])
        return "\n".join(lines) + "\n"


class WorkspaceDoctor:
    """Read-mostly release diagnostics for the local Workspace installation."""

    def __init__(self, workspace_root: Path, data_dir: Path | None = None) -> None:
        self.workspace_root = workspace_root.resolve()
        self.ecosystem_root = self.workspace_root.parent
        self.settings = SettingsStore(data_dir)
        self.config_path = self.workspace_root / "config" / "modules.json"
        self.checks: list[DoctorCheck] = []

    def run(self) -> DoctorReport:
        self.checks = []
        self._check_runtime()
        self._check_essential_files()
        self._check_data_directory()
        settings = self.settings.load()
        self._check_settings()
        self._check_configured_paths(settings)
        registry = self._check_registry()
        self._check_module_sdk()
        if registry is not None:
            self._check_modules(registry, settings)
            self._check_ports_and_services(registry, settings)
        self._check_persisted_json()
        self._check_stale_uploads()
        self._check_databases(settings)
        return DoctorReport(tuple(self.checks))

    def _add(self, level: str, title: str, detail: str = "", code: str = "") -> None:
        self.checks.append(DoctorCheck(level, title, detail, code))

    def _check_runtime(self) -> None:
        version = sys.version_info
        level = "ok" if version >= (3, 11) else "error"
        self._add(level, f"Python {version.major}.{version.minor}.{version.micro}", str(Path(sys.executable)), "PYTHON_VERSION")
        for label, code, candidates in (
            ("Node.js", "NODE_VERSION", ("node.exe", "node")),
            ("npm", "NPM_VERSION", ("npm.cmd", "npm")),
            ("Git", "GIT_VERSION", ("git.exe", "git")),
        ):
            executable = next((shutil.which(item) for item in candidates if shutil.which(item)), None)
            if not executable:
                self._add("warning", f"{label} não detectado", "Recursos que dependem dele continuarão opcionais.", code.replace("_VERSION", "_MISSING"))
                continue
            version_text = self._command_version(executable)
            self._add("ok", f"{label} {version_text}".strip(), executable, code)

    def _check_essential_files(self) -> None:
        paths = {
            "launcher.py": self.workspace_root / "launcher.py",
            "config/modules.json": self.config_path,
            "web/index.html": self.workspace_root / "web" / "index.html",
            "Core Python": self.workspace_root / "workspace_os" / "server.py",
        }
        design_system = self.ecosystem_root / "workspace-design-system" / "src" / "workspace-ui.css"
        fallback = self.workspace_root / "web" / "workspace-ui-fallback.css"
        if not design_system.is_file() and not fallback.is_file():
            paths["Design System"] = design_system
        missing = [label for label, path in paths.items() if not path.is_file()]
        if missing:
            self._add("error", "Arquivos essenciais ausentes", ", ".join(missing), "ESSENTIAL_FILES_MISSING")
        else:
            self._add("ok", "Arquivos essenciais", f"{len(paths)} arquivos verificados", "ESSENTIAL_FILES_OK")

    def _check_data_directory(self) -> None:
        result: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

        def probe() -> None:
            try:
                self.settings.data_dir.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(prefix="workspace-doctor-", dir=self.settings.data_dir, delete=True):
                    pass
                result.put((True, shutil.disk_usage(self.settings.data_dir)))
            except OSError as exc:
                result.put((False, exc))

        worker = threading.Thread(target=probe, name="workspace-doctor-data-probe", daemon=True)
        worker.start()
        worker.join(timeout=3)
        if worker.is_alive():
            self._add(
                "error", "Diretório de dados não respondeu",
                f"{self.settings.data_dir}: a verificação excedeu 3 segundos.", "DATA_DIR_TIMEOUT",
            )
            return
        writable, value = result.get_nowait()
        if not writable:
            self._add("error", "Diretório de dados sem escrita", f"{self.settings.data_dir}: {value}", "DATA_DIR_UNWRITABLE")
            return
        usage = value
        if usage.free < 1024 * 1024 * 1024:
            self._add("warning", "Pouco espaço no diretório de dados", self._format_bytes(usage.free) + " livres", "LOW_DISK")
        else:
            self._add("ok", "Diretório de dados gravável", f"{self.settings.data_dir} ({self._format_bytes(usage.free)} livres)", "DATA_DIR_OK")

    def _check_settings(self) -> None:
        status = self.settings.load_status()
        if not status["exists"]:
            self._add("ok", "Configuração ainda não criada", "Defaults seguros serão usados.", "SETTINGS_DEFAULTS")
        elif status["valid"]:
            self._add("ok", "Configuração válida", str(self.settings.path), "SETTINGS_OK")
        else:
            self._add("error", "Configuração recuperada parcialmente", "; ".join(status["issues"][:3]), "SETTINGS_RECOVERED")

    def _check_registry(self) -> ModuleRegistry | None:
        try:
            registry = ModuleRegistry(self.config_path, self.ecosystem_root)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self._add("error", "Registro central inválido", str(exc), "REGISTRY_INVALID")
            return None
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
            raw_origin = raw.get("origin", {}) if isinstance(raw, dict) else {}
            scheme = raw_origin.get("scheme", "http") if isinstance(raw_origin, dict) else ""
            host = raw_origin.get("host", "127.0.0.1") if isinstance(raw_origin, dict) else ""
            port = int(raw_origin.get("port", 8790)) if isinstance(raw_origin, dict) else 0
            if scheme != "http" or host not in {"127.0.0.1", "localhost", "::1"} or not 1 <= port <= 65535:
                self._add("error", "Origem central inválida", "Use HTTP, um host loopback e uma porta entre 1 e 65535.", "ORIGIN_INVALID")
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            pass
        if registry.discovery_errors:
            self._add("error", "Manifestos inválidos", f"{len(registry.discovery_errors)} erro(s); primeiro: {registry.discovery_errors[0]}", "MANIFEST_INVALID")
        else:
            self._add("ok", f"{len(registry.modules)} módulos detectados", "Todos os manifestos foram aceitos.", "MODULES_OK")
        return registry

    def _check_module_sdk(self) -> None:
        report = validate_modules(self.ecosystem_root, self.config_path)
        if report.errors:
            error_messages = [issue.message for issue in report.global_issues if issue.level == "error"]
            error_messages.extend(
                issue.message
                for module in report.modules
                for issue in module.issues
                if issue.level == "error"
            )
            first = error_messages[0]
            self._add(
                "error", "Validação do SDK de módulos falhou",
                f"{report.errors} erro(s); primeiro: {first}", "MODULE_SDK_INVALID",
            )
        elif report.warnings:
            self._add(
                "warning", "Validação do SDK de módulos encontrou avisos",
                f"{report.warnings} aviso(s). Execute `npm run validate-modules` para detalhes.",
                "MODULE_SDK_WARNINGS",
            )
        else:
            self._add(
                "ok", "Contrato do SDK de módulos",
                f"{len(report.modules)} manifesto(s) verificado(s).", "MODULE_SDK_OK",
            )

    def _check_modules(self, registry: ModuleRegistry, settings: dict[str, Any]) -> None:
        missing_entries: list[str] = []
        missing_commands: list[str] = []
        incompatible: list[str] = []
        serialized = {item["id"]: item for item in registry.serialize(effective_module_urls(settings))}
        for module in registry.modules.values():
            if module.project_path and not module.project_path.is_dir():
                missing_entries.append(f"{module.id}: pasta ausente")
            elif module.entry_file and module.project_path and not (module.project_path / module.entry_file).is_file():
                missing_entries.append(f"{module.id}: {module.entry_file}")
            if module.command:
                executable = self._command_executable(module)
                if not executable:
                    missing_commands.append(f"{module.id}: {module.command[0]}")
            if not serialized[module.id]["compatible"]:
                incompatible.append(f"{module.id} requer Core {module.min_core_version}")
        if missing_entries:
            self._add("error", "Entradas de módulos ausentes", "; ".join(missing_entries[:6]), "MODULE_ENTRY_MISSING")
        else:
            self._add("ok", "Entradas de módulos", "Pastas e arquivos iniciais existem.", "MODULE_ENTRIES_OK")
        if missing_commands:
            self._add("error", "Executáveis de módulos ausentes", "; ".join(missing_commands), "MODULE_COMMAND_MISSING")
        else:
            self._add("ok", "Dependências de inicialização", "Comandos dos serviços confiáveis foram encontrados.", "MODULE_COMMANDS_OK")
        if incompatible:
            self._add("error", "Módulos incompatíveis", "; ".join(incompatible), "MODULE_INCOMPATIBLE")

    def _check_ports_and_services(self, registry: ModuleRegistry, settings: dict[str, Any]) -> None:
        origin = registry.core_origin
        core_health = self._http_health(f"{origin.url}/api/health", expect_workspace=True)
        if core_health == "ok":
            self._add("ok", f"Core já ativo na porta {origin.port}", origin.url, "CORE_RUNNING")
        elif self._port_open(origin.host, origin.port):
            self._add("error", f"Porta {origin.port} ocupada por outro processo", "O endpoint /api/health do Workspace não respondeu.", "CORE_PORT_CONFLICT")
        else:
            self._add("ok", f"Porta {origin.port} disponível para o Core", origin.url, "CORE_PORT_FREE")

        custom_urls = effective_module_urls(settings)
        unavailable: list[str] = []
        available: list[str] = []
        ports: dict[int, list[str]] = {}
        for module in registry.modules.values():
            if module.kind != "web-service":
                continue
            url = custom_urls.get(module.id) or module.health_url or module.service_url or module.url
            if url:
                parsed = urlparse(url)
                try:
                    port = parsed.port or (443 if parsed.scheme == "https" else 80)
                    ports.setdefault(port, []).append(module.name)
                except ValueError:
                    pass
            if self._http_health(url) == "ok":
                available.append(module.name)
            else:
                unavailable.append(module.name)
        if available:
            self._add("ok", "Serviços locais ativos", ", ".join(available), "SERVICES_ACTIVE")
        if unavailable:
            self._add("warning", "Serviços locais indisponíveis", ", ".join(unavailable) + ". São opcionais para iniciar o Core.", "SERVICES_UNAVAILABLE")
        conflicts = [f"{port}: {', '.join(names)}" for port, names in ports.items() if len(set(names)) > 1]
        if conflicts:
            self._add("error", "Conflitos de porta entre serviços", "; ".join(conflicts), "SERVICE_PORT_CONFLICT")

    def _check_configured_paths(self, settings: dict[str, Any]) -> None:
        configs = settings.get("module_configs", {})
        bridge = configs.get("bridge", {})
        driver = configs.get("drive2", {})
        missing: list[str] = []
        for key in ("data_dir", "received_dir", "tls_cert", "tls_key"):
            value = str(bridge.get(key, "")).strip()
            if value and not self._module_path("bridge", value).exists():
                missing.append(f"bridge.{key}")
        for key in ("storage_root", "temp_root", "trash_root", "emails_root", "attachments_root"):
            value = str(driver.get(key, "")).strip()
            if value and not self._module_path("driver", value).exists():
                missing.append(f"drive2.{key}")
        if missing:
            self._add("warning", "Caminhos configurados ainda não existem", ", ".join(missing), "CONFIGURED_PATH_MISSING")
        else:
            self._add("ok", "Caminhos configurados", "Nenhum caminho explícito inválido foi encontrado.", "CONFIGURED_PATHS_OK")

    def _check_persisted_json(self) -> None:
        candidates = [
            self.settings.data_dir / "activity.json",
            self.settings.data_dir / "blackbox.json",
            self.settings.data_dir / "clipboard.json",
            self.settings.data_dir / "presets.json",
            self.settings.data_dir / "dropzone" / "history.json",
        ]
        candidates.extend((self.settings.data_dir / "module-data").glob("*.json") if (self.settings.data_dir / "module-data").is_dir() else [])
        invalid: list[str] = []
        checked = 0
        for path in candidates:
            if not path.is_file():
                continue
            checked += 1
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                invalid.append(path.name)
        if invalid:
            self._add("error", "JSONs persistidos inválidos", ", ".join(invalid[:8]), "PERSISTED_JSON_INVALID")
        else:
            self._add("ok", "Integridade dos JSONs persistidos", f"{checked} arquivo(s) verificado(s)", "PERSISTED_JSON_OK")

    def _check_stale_uploads(self) -> None:
        root = self.settings.data_dir / "dropzone" / ".uploads"
        leftovers = list(root.glob("*")) if root.is_dir() else []
        if leftovers:
            total = sum(path.stat().st_size for path in leftovers if path.is_file())
            self._add("warning", "Uploads incompletos na Drop Zone", f"{len(leftovers)} item(ns), {self._format_bytes(total)}", "STALE_UPLOADS")

    def _check_databases(self, settings: dict[str, Any]) -> None:
        bridge_config = settings.get("module_configs", {}).get("bridge", {})
        driver_config = settings.get("module_configs", {}).get("drive2", {})
        bridge_dir = self._module_path("bridge", str(bridge_config.get("data_dir", "")) or ".data")
        driver_db = self._module_path("driver", str(driver_config.get("database", "")) or "drive2.db")
        databases = [bridge_dir / "bridge.sqlite3", driver_db]
        existing = [path for path in databases if path.is_file()]
        invalid: list[str] = []
        for path in existing:
            try:
                connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=2)
                try:
                    result = connection.execute("PRAGMA quick_check").fetchone()
                finally:
                    connection.close()
                if not result or str(result[0]).lower() != "ok":
                    invalid.append(path.name)
            except sqlite3.Error:
                invalid.append(path.name)
        if invalid:
            self._add("error", "Bancos SQLite com falha de integridade", ", ".join(invalid), "SQLITE_INVALID")
        elif existing:
            self._add("ok", "Integridade dos bancos locais", f"{len(existing)} banco(s) verificado(s)", "SQLITE_OK")
        else:
            self._add("warning", "Bancos locais ainda não criados", "Bridge e InkDriver criarão seus bancos no primeiro uso.", "SQLITE_MISSING")

    def _command_executable(self, module: ModuleDefinition) -> str | None:
        if not module.command:
            return None
        project = module.project_path or self.workspace_root
        replacements = {
            "{python}": Path(sys.executable),
            "{pythonw}": Path(sys.executable).with_name("pythonw.exe") if os.name == "nt" else Path(sys.executable),
            "{project_python}": project / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"),
            "{project}": project,
            "{workspace}": self.workspace_root,
            "{ecosystem}": self.ecosystem_root,
        }
        raw = module.command[0]
        expanded = raw
        for token, value in replacements.items():
            expanded = expanded.replace(token, str(value))
        path = Path(expanded)
        if path.is_absolute() or any(separator in expanded for separator in ("/", "\\")):
            if not path.is_absolute():
                path = project / path
            return str(path.resolve()) if path.is_file() else None
        return shutil.which(expanded)

    def _module_path(self, module_folder: str, configured: str) -> Path:
        path = Path(configured).expanduser()
        return path.resolve() if path.is_absolute() else (self.ecosystem_root / module_folder / path).resolve()

    @staticmethod
    def _command_version(executable: str) -> str:
        try:
            completed = subprocess.run(
                [executable, "--version"], capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            return "detectado"
        return (completed.stdout or completed.stderr).strip().splitlines()[0][:80] if (completed.stdout or completed.stderr).strip() else "detectado"

    @staticmethod
    def _http_health(url: str | None, *, expect_workspace: bool = False) -> str:
        if not url:
            return "missing"
        try:
            with urlopen(url, timeout=0.7) as response:
                if not 200 <= response.status < 300:
                    return "failed"
                if expect_workspace:
                    payload = json.load(response)
                    return "ok" if isinstance(payload, dict) and payload.get("status") == "ok" else "failed"
                return "ok"
        except HTTPError:
            return "failed"
        except (OSError, URLError, ValueError):
            return "failed"

    @staticmethod
    def _port_open(host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except OSError:
            return False

    @staticmethod
    def _format_bytes(value: int) -> str:
        size = float(value)
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if size < 1024 or unit == "TiB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024
        return f"{int(value)} B"


def print_report(report: DoctorReport, stream: TextIO = sys.stdout) -> None:
    try:
        stream.write(report.render())
    except UnicodeEncodeError:
        stream.write(report.render(ascii_only=True))
