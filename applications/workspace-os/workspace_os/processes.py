from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import IO

from .registry import ModuleDefinition, ModuleRegistry
from .observability import StructuredModuleLogs


class ProcessManager:
    def __init__(self, registry: ModuleRegistry, data_dir: Path, workspace_root: Path, logs: StructuredModuleLogs | None = None) -> None:
        self.registry = registry
        self.data_dir = data_dir
        self.workspace_root = workspace_root.resolve()
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._logs: dict[str, IO[bytes]] = {}
        self._lock = threading.RLock()
        self.structured_logs = logs or StructuredModuleLogs(data_dir)

    def start(
        self,
        module_id: str,
        custom_url: str | None = None,
        module_config: dict[str, object] | None = None,
    ) -> dict[str, object]:
        module = self.registry.get(module_id)
        health_url = custom_url or module.health_url or module.url
        if ModuleRegistry.is_reachable(health_url):
            self.structured_logs.write(module_id, "process.start.skipped", message="Serviço já alcançável", url=health_url)
            return {"ok": True, "message": f"{module.name} já está ativo.", "alreadyRunning": True}
        if not module.command:
            raise ValueError(f"{module.name} não possui comando local de inicialização.")
        if not module.installed or not module.project_path:
            raise FileNotFoundError(f"A pasta de {module.name} não foi encontrada.")
        with self._lock:
            existing = self._processes.get(module_id)
            if existing and existing.poll() is None:
                return {"ok": True, "message": f"{module.name} está iniciando.", "alreadyRunning": True}
            command = self._expand_command(module)
            executable = command[0]
            if not Path(executable).is_absolute():
                resolved = shutil.which(executable)
                if not resolved:
                    raise FileNotFoundError(f"Executável não encontrado: {executable}")
                command[0] = resolved
            log_dir = self.data_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            output_log = log_dir / f"{module_id}.log"
            self._rotate_output_log(output_log)
            log_handle = output_log.open("ab")
            flags = 0
            startup_info = None
            if os.name == "nt":
                flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
                startup_info = subprocess.STARTUPINFO()
                startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            environment = os.environ.copy()
            core_origin = getattr(self.registry, "core_origin", None)
            if core_origin:
                environment["WORKSPACE_CORE_ORIGIN"] = core_origin.url
            environment.update(self._module_environment(module_id, module_config or {}))
            try:
                process = subprocess.Popen(
                    command,
                    cwd=module.project_path,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    creationflags=flags,
                    startupinfo=startup_info,
                    env=environment,
                )
            except OSError as exc:
                log_handle.close()
                self.structured_logs.write(module_id, "process.start.failed", level="error", error=str(exc))
                raise
            self._processes[module_id] = process
            old_log = self._logs.pop(module_id, None)
            if old_log:
                old_log.close()
            self._logs[module_id] = log_handle
            self.structured_logs.write(module_id, "process.started", pid=process.pid, command=command[0])
            threading.Thread(
                target=self._watch_process,
                args=(module_id, process, log_handle),
                name=f"workspace-process-{module_id}",
                daemon=True,
            ).start()
            return {"ok": True, "message": f"{module.name} foi iniciado.", "pid": process.pid}

    def stop(self, module_id: str) -> dict[str, object]:
        module = self.registry.get(module_id)
        with self._lock:
            process = self._processes.get(module_id)
            if not process or process.poll() is not None:
                self.structured_logs.write(module_id, "process.stop.skipped", level="warning", message="Processo não gerenciado nesta sessão")
                return {
                    "ok": False,
                    "message": f"{module.name} não foi iniciado por esta sessão do Workspace OS.",
                }
            self._terminate_process_tree(process)
            self._processes.pop(module_id, None)
            log_handle = self._logs.pop(module_id, None)
            if log_handle:
                log_handle.close()
            self.structured_logs.write(module_id, "process.stopped", pid=process.pid, exitCode=process.returncode)
            return {"ok": True, "message": f"{module.name} foi encerrado."}

    def stop_all(self) -> None:
        with self._lock:
            running = [
                module_id
                for module_id, process in self._processes.items()
                if process.poll() is None
            ]
        for module_id in running:
            try:
                self.stop(module_id)
            except (OSError, subprocess.SubprocessError):
                continue

    def _watch_process(
        self, module_id: str, process: subprocess.Popen[bytes], log_handle: IO[bytes],
    ) -> None:
        """Release process and log handles when a managed service exits on its own."""
        try:
            process.wait()
        finally:
            with self._lock:
                still_managed = self._processes.get(module_id) is process
                if still_managed:
                    self._processes.pop(module_id, None)
                    if self._logs.get(module_id) is log_handle:
                        self._logs.pop(module_id, None)
                if not log_handle.closed:
                    log_handle.close()
            if still_managed:
                self.structured_logs.write(
                    module_id,
                    "process.exited",
                    level="warning" if process.returncode else "info",
                    pid=process.pid,
                    exitCode=process.returncode,
                )

    def managed_state(self, module_id: str) -> str:
        with self._lock:
            process = self._processes.get(module_id)
            if not process:
                return "external-or-stopped"
            return "running" if process.poll() is None else "stopped"

    def start_configured(
        self,
        module_ids: list[str],
        custom_urls: dict[str, str],
        module_configs: dict[str, dict[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        results = []
        module_configs = module_configs or {}
        for module_id in module_ids:
            if module_id not in self.registry.modules:
                results.append({"ok": False, "module": module_id, "message": "Módulo desconhecido."})
                continue
            try:
                result = self.start(module_id, custom_urls.get(module_id), module_configs.get(module_id))
                result["module"] = module_id
                results.append(result)
            except (OSError, ValueError) as exc:
                results.append({"ok": False, "module": module_id, "message": str(exc)})
        return results

    @staticmethod
    def _module_environment(module_id: str, config: dict[str, object]) -> dict[str, str]:
        if module_id == "bridge":
            mapping = {
                "host": "BRIDGE_HOST", "port": "BRIDGE_PORT", "public_url": "BRIDGE_PUBLIC_URL",
                "discovery_port": "BRIDGE_DISCOVERY_PORT", "data_dir": "BRIDGE_DATA_DIR",
                "received_dir": "BRIDGE_RECEIVED_DIR", "tls_cert": "BRIDGE_TLS_CERT", "tls_key": "BRIDGE_TLS_KEY",
            }
            environment = {
                env_name: str(config[key])
                for key, env_name in mapping.items()
                if key in config and str(config[key]).strip()
            }
            if "max_chunk_mb" in config:
                environment["BRIDGE_MAX_CHUNK"] = str(int(config["max_chunk_mb"]) * 1024 * 1024)
            return environment
        if module_id == "drive2":
            mapping = {
                "host": "DRIVE2_HOST", "port": "DRIVE2_PORT", "storage_root": "DRIVE2_STORAGE_ROOT",
                "database": "DRIVE2_DATABASE", "temp_root": "DRIVE2_TEMP_ROOT",
                "trash_root": "DRIVE2_TRASH_ROOT", "emails_root": "DRIVE2_EMAILS_ROOT",
                "attachments_root": "DRIVE2_ATTACHMENTS_ROOT", "log_level": "DRIVE2_LOG_LEVEL",
                "max_upload_mb": "DRIVE2_MAX_UPLOAD_MB", "scan_interval_seconds": "DRIVE2_SCAN_INTERVAL_SECONDS",
                "sync_interval_seconds": "DRIVE2_SYNC_INTERVAL_SECONDS", "sync_max_retries": "DRIVE2_SYNC_MAX_RETRIES",
                "tailscale_only": "DRIVE2_TAILSCALE_ONLY", "auth_enabled": "DRIVE2_AUTH_ENABLED",
                "auth_username": "DRIVE2_AUTH_USERNAME", "auth_cookie_secure": "DRIVE2_AUTH_COOKIE_SECURE",
                "auth_session_hours": "DRIVE2_AUTH_SESSION_HOURS", "r2_enabled": "R2_ENABLED",
                "r2_region": "R2_REGION", "r2_prefix": "R2_PREFIX", "gmail_enabled": "GMAIL_ENABLED",
                "gmail_credentials_path": "GMAIL_CREDENTIALS_PATH", "gmail_token_path": "GMAIL_TOKEN_PATH",
                "gmail_archive_after_days": "GMAIL_ARCHIVE_AFTER_DAYS", "gmail_max_message_mb": "GMAIL_MAX_MESSAGE_MB",
                "gmail_protect_starred": "GMAIL_PROTECT_STARRED", "gmail_protect_important": "GMAIL_PROTECT_IMPORTANT",
                "gmail_trash_after_backup": "GMAIL_TRASH_AFTER_BACKUP",
            }
            environment = {
                env_name: str(config[key])
                for key, env_name in mapping.items()
                if key in config and str(config[key]).strip()
            }
            if config.get("run_local", True):
                environment["DRIVE2_HOST"] = "127.0.0.1"
                environment["DRIVE2_AUTH_COOKIE_SECURE"] = "false"
            return environment
        return {}

    def _expand_command(self, module: ModuleDefinition) -> list[str]:
        project = module.project_path or self.workspace_root
        python = Path(sys.executable).resolve()
        pythonw = python.with_name("pythonw.exe") if os.name == "nt" else python
        project_python = project / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        replacements = {
            "{python}": str(python),
            "{pythonw}": str(pythonw if pythonw.exists() else python),
            "{project_python}": str(project_python),
            "{project}": str(project),
            "{workspace}": str(self.workspace_root),
            "{ecosystem}": str(self.registry.ecosystem_root),
        }
        expanded: list[str] = []
        for part in module.command:
            value = part
            for token, replacement in replacements.items():
                value = value.replace(token, replacement)
            expanded.append(value)
        return expanded

    @staticmethod
    def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
        if os.name == "nt":
            completed = subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
                check=False,
            )
            if completed.returncode == 0:
                try:
                    process.wait(timeout=2)
                    return
                except subprocess.TimeoutExpired:
                    pass
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    @staticmethod
    def _rotate_output_log(path: Path, *, max_bytes: int = 5 * 1024 * 1024, backups: int = 2) -> None:
        try:
            if path.stat().st_size < max_bytes:
                return
        except FileNotFoundError:
            return
        oldest = path.with_suffix(path.suffix + f".{backups}")
        oldest.unlink(missing_ok=True)
        for index in range(backups - 1, 0, -1):
            source = path.with_suffix(path.suffix + f".{index}")
            if source.exists():
                source.replace(path.with_suffix(path.suffix + f".{index + 1}"))
        path.replace(path.with_suffix(path.suffix + ".1"))
