from __future__ import annotations

import hashlib
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .observability import StructuredModuleLogs


SENSITIVE_COMMAND = re.compile(
    r"(?:password|passwd|token|secret|api[_-]?key|authorization)(?:\s|=|:)+\S+",
    re.IGNORECASE,
)
EXECUTABLE_SUFFIXES = {".exe", ".com", ".cmd", ".bat", ".ps1"}
COMMON_COMMANDS = (
    "cmd", "git", "node", "npm", "npx", "powershell", "pwsh", "py", "python",
)


def _decode(value: bytes, encoding: str | None) -> str:
    for candidate in ("utf-8", encoding, "mbcs" if os.name == "nt" else None):
        if not candidate:
            continue
        try:
            return value.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    return value.decode("utf-8", errors="replace")


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _command_for_audit(command: str) -> tuple[str, str]:
    digest = hashlib.sha256(command.encode("utf-8", errors="replace")).hexdigest()[:20]
    return ("[redigido: possível credencial]" if SENSITIVE_COMMAND.search(command) else command, digest)


def _windows_resources(process: subprocess.Popen[bytes]) -> dict[str, int | float | None]:
    if os.name != "nt":
        return {"workingSetBytes": None, "peakWorkingSetBytes": None, "cpuSeconds": None}
    try:
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        handle = wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
        memory_ok = ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        times_ok = ctypes.windll.kernel32.GetProcessTimes(
            handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user),
        )

        def filetime_seconds(value: wintypes.FILETIME) -> float:
            ticks = (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)
            return round(ticks / 10_000_000, 3)

        return {
            "workingSetBytes": int(counters.WorkingSetSize) if memory_ok else None,
            "peakWorkingSetBytes": int(counters.PeakWorkingSetSize) if memory_ok else None,
            "cpuSeconds": round(filetime_seconds(kernel) + filetime_seconds(user), 3) if times_ok else None,
        }
    except (AttributeError, OSError, TypeError, ValueError):
        return {"workingSetBytes": None, "peakWorkingSetBytes": None, "cpuSeconds": None}


def _posix_resources(process: subprocess.Popen[bytes]) -> dict[str, int | float | None]:
    if os.name == "nt":
        return _windows_resources(process)
    try:
        stat = Path(f"/proc/{process.pid}/stat").read_text(encoding="ascii").split()
        page_size = os.sysconf("SC_PAGE_SIZE")
        clock_ticks = os.sysconf("SC_CLK_TCK")
        resident = int(Path(f"/proc/{process.pid}/statm").read_text(encoding="ascii").split()[1]) * page_size
        return {
            "workingSetBytes": resident,
            "peakWorkingSetBytes": resident,
            "cpuSeconds": round((int(stat[13]) + int(stat[14])) / clock_ticks, 3),
        }
    except (FileNotFoundError, IndexError, OSError, ValueError):
        return {"workingSetBytes": None, "peakWorkingSetBytes": None, "cpuSeconds": None}


@dataclass
class TerminalExecution:
    id: str
    session_id: str
    command: str
    cwd: Path
    process: subprocess.Popen[bytes]
    permission: str
    risk: str
    output_encoding: str | None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_monotonic: float = field(default_factory=time.monotonic)
    ended_monotonic: float | None = None
    status: str = "running"
    exit_code: int | None = None
    stdout: bytearray = field(default_factory=bytearray)
    stderr: bytearray = field(default_factory=bytearray)
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    cancel_requested: bool = False
    timed_out: bool = False
    resources: dict[str, int | float | None] = field(default_factory=dict)
    reader_threads: list[threading.Thread] = field(default_factory=list, repr=False)


class TerminalExecutionManager:
    """Runs bounded terminal processes and exposes safe polling/cancellation."""

    def __init__(
        self,
        ecosystem_root: Path,
        logs: StructuredModuleLogs,
        *,
        max_output_bytes: int = 2 * 1024 * 1024,
        max_records: int = 100,
        max_active: int = 8,
        retention_seconds: int = 30 * 60,
        max_runtime_seconds: int = 4 * 60 * 60,
    ) -> None:
        self.ecosystem_root = ecosystem_root.resolve()
        self.logs = logs
        self.max_output_bytes = max_output_bytes
        self.max_records = max_records
        self.max_active = max_active
        self.retention_seconds = retention_seconds
        self.max_runtime_seconds = max_runtime_seconds
        self._records: dict[str, TerminalExecution] = {}
        self._lock = threading.RLock()
        self._commands_cache: list[str] = list(COMMON_COMMANDS)
        self._commands_cached_at = 0.0
        self._commands_loading = False
        self._starting = 0
        self._starting_sessions: set[str] = set()

    def start(
        self,
        *,
        args: list[str],
        cwd: Path,
        environment: dict[str, str],
        command: str,
        session_id: str,
        permission: str,
        risk: str,
        output_encoding: str | None = None,
    ) -> dict[str, Any]:
        self._cleanup()
        execution_id = uuid.uuid4().hex
        safe_session = re.sub(r"[^A-Za-z0-9_.-]", "", session_id)[:80] or "default"
        with self._lock:
            active = [record for record in self._records.values() if record.status == "running"]
            if safe_session in self._starting_sessions or any(record.session_id == safe_session for record in active):
                raise RuntimeError("Esta aba já possui um processo em execução.")
            if len(active) + self._starting >= self.max_active:
                raise RuntimeError(f"O limite de {self.max_active} processos simultâneos foi atingido.")
            self._starting += 1
            self._starting_sessions.add(safe_session)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if os.name == "nt":
            creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            process = subprocess.Popen(
                args,
                cwd=cwd,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                start_new_session=os.name != "nt",
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            with self._lock:
                self._starting -= 1
                self._starting_sessions.discard(safe_session)
            raise
        record = TerminalExecution(
            id=execution_id,
            session_id=safe_session,
            command=command,
            cwd=cwd,
            process=process,
            permission=permission,
            risk=risk,
            output_encoding=output_encoding,
        )
        with self._lock:
            self._records[execution_id] = record
            self._starting -= 1
            self._starting_sessions.discard(safe_session)
        audit_command, command_hash = _command_for_audit(command)
        self.logs.write(
            "terminal", "terminal.execution.started", executionId=execution_id,
            sessionId=safe_session, pid=process.pid, cwd=str(cwd), command=audit_command,
            commandHash=command_hash, permission=permission, risk=risk,
        )
        record.reader_threads = [
            threading.Thread(target=self._read_stream, args=(record, "stdout"), daemon=True),
            threading.Thread(target=self._read_stream, args=(record, "stderr"), daemon=True),
        ]
        for reader in record.reader_threads:
            reader.start()
        threading.Thread(target=self._wait, args=(record,), daemon=True).start()
        return self.snapshot(execution_id)

    def snapshot(self, execution_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._records.get(execution_id)
            if record is None:
                raise KeyError(execution_id)
            process = record.process
        resources = _posix_resources(process)
        with self._lock:
            if record.status == "running":
                record.resources = self._merge_resources(record.resources, resources)
            elapsed_end = record.ended_monotonic or time.monotonic()
            duration_ms = max(0, round((elapsed_end - record.started_monotonic) * 1000))
            stdout = _decode(bytes(record.stdout), record.output_encoding).splitlines()[-2000:]
            stderr = _decode(bytes(record.stderr), record.output_encoding).splitlines()[-2000:]
            return {
                "ok": record.status == "completed" and record.exit_code == 0,
                "executionId": record.id,
                "sessionId": record.session_id,
                "status": record.status,
                "pid": record.process.pid,
                "cwd": str(record.cwd),
                "startedAt": record.started_at,
                "durationMs": duration_ms,
                "exitCode": record.exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "outputTruncated": record.stdout_truncated or record.stderr_truncated,
                "permission": record.permission,
                "risk": record.risk,
                "resources": dict(record.resources),
            }

    def cancel(self, execution_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._records.get(execution_id)
            if record is None:
                raise KeyError(execution_id)
            if record.status != "running":
                return self.snapshot(execution_id)
            record.cancel_requested = True
            process = record.process
        self._terminate_tree(process)
        return self.snapshot(execution_id)

    def cancel_all(self) -> None:
        with self._lock:
            identifiers = [item.id for item in self._records.values() if item.status == "running"]
        for execution_id in identifiers:
            try:
                self.cancel(execution_id)
            except (KeyError, OSError):
                continue

    def completions(self, raw: str, cwd: Path, limit: int = 30) -> list[dict[str, str]]:
        if not _inside(cwd, self.ecosystem_root):
            return []
        raw = raw[-1024:]
        token_start = max(raw.rfind(" "), raw.rfind("\t")) + 1
        fragment = raw[token_start:].strip('"\'')
        if token_start == 0 and not any(character in fragment for character in ("/", "\\")):
            wanted = fragment.casefold()
            return [
                {"value": command, "description": "comando disponível no sistema"}
                for command in self._available_commands()
                if command.casefold().startswith(wanted)
            ][:limit]

        parent_text, _, name_prefix = fragment.replace("\\", "/").rpartition("/")
        parent = (cwd / parent_text).resolve() if parent_text else cwd
        if not parent.is_dir() or not _inside(parent, self.ecosystem_root):
            return []
        results: list[dict[str, str]] = []
        try:
            children = sorted(parent.iterdir(), key=lambda item: (not item.is_dir(), item.name.casefold()))
        except OSError:
            return []
        for child in children:
            if not child.name.casefold().startswith(name_prefix.casefold()):
                continue
            relative = f"{parent_text}/{child.name}" if parent_text else child.name
            relative = relative.replace("/", os.sep)
            if child.is_dir():
                relative += os.sep
            if " " in relative:
                relative = f'"{relative}"'
            results.append({
                "value": raw[:token_start] + relative,
                "description": "pasta" if child.is_dir() else "arquivo",
            })
            if len(results) >= limit:
                break
        return results

    def _available_commands(self) -> list[str]:
        now = time.monotonic()
        with self._lock:
            if now - self._commands_cached_at < 60:
                return list(self._commands_cache)
            if not self._commands_loading:
                self._commands_loading = True
                threading.Thread(
                    target=self._refresh_available_commands,
                    name="workspace-command-discovery",
                    daemon=True,
                ).start()
            return list(self._commands_cache)

    def _refresh_available_commands(self) -> None:
        try:
            ordered = self._discover_available_commands()
            with self._lock:
                self._commands_cache = ordered
                self._commands_cached_at = time.monotonic()
        finally:
            with self._lock:
                self._commands_loading = False

    def _discover_available_commands(self) -> list[str]:
        commands: set[str] = set(COMMON_COMMANDS)
        for directory_text in os.environ.get("PATH", "").split(os.pathsep):
            directory = Path(directory_text.strip('"'))
            try:
                if not directory.is_dir():
                    continue
                for entry in directory.iterdir():
                    if entry.is_file() and (os.name != "nt" or entry.suffix.lower() in EXECUTABLE_SUFFIXES):
                        commands.add(entry.stem if entry.suffix.lower() in EXECUTABLE_SUFFIXES else entry.name)
            except OSError:
                continue
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if powershell:
            try:
                completed = subprocess.run(
                    [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command",
                     "Get-Command -CommandType Alias,Cmdlet,Function | Select-Object -ExpandProperty Name"],
                    capture_output=True, timeout=4, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                commands.update(_decode(completed.stdout, None).splitlines())
            except (OSError, subprocess.TimeoutExpired):
                pass
        ordered = sorted((item.strip() for item in commands if item.strip()), key=str.casefold)
        return ordered

    def _read_stream(self, record: TerminalExecution, name: str) -> None:
        stream = getattr(record.process, name)
        if stream is None:
            return
        try:
            while True:
                chunk = stream.read1(4096) if hasattr(stream, "read1") else stream.read(4096)
                if not chunk:
                    break
                with self._lock:
                    target = getattr(record, name)
                    target.extend(chunk)
                    overflow = len(target) - self.max_output_bytes
                    if overflow > 0:
                        del target[:overflow]
                        setattr(record, f"{name}_truncated", True)
        finally:
            stream.close()

    def _wait(self, record: TerminalExecution) -> None:
        try:
            record.process.wait(timeout=self.max_runtime_seconds)
        except subprocess.TimeoutExpired:
            with self._lock:
                record.timed_out = True
                record.cancel_requested = True
            self._terminate_tree(record.process)
            record.process.wait()
        for reader in record.reader_threads:
            reader.join(timeout=2)
        resources = _posix_resources(record.process)
        with self._lock:
            record.resources = self._merge_resources(record.resources, resources)
            record.exit_code = record.process.returncode
            record.ended_monotonic = time.monotonic()
            if record.timed_out:
                record.status = "timed_out"
            elif record.cancel_requested:
                record.status = "cancelled"
            else:
                record.status = "completed"
            status = record.status
            duration_ms = round((record.ended_monotonic - record.started_monotonic) * 1000)
        self.logs.write(
            "terminal", f"terminal.execution.{status}",
            level="error" if status in {"timed_out"} or (record.exit_code or 0) != 0 else "info",
            executionId=record.id, sessionId=record.session_id, pid=record.process.pid,
            exitCode=record.exit_code, durationMs=duration_ms, resources=record.resources,
        )

    @staticmethod
    def _merge_resources(
        current: dict[str, int | float | None], incoming: dict[str, int | float | None],
    ) -> dict[str, int | float | None]:
        merged = dict(current)
        for key, value in incoming.items():
            if value is None:
                continue
            if key == "peakWorkingSetBytes":
                merged[key] = max(int(merged.get(key) or 0), int(value))
            else:
                merged[key] = value
        return merged

    def _cleanup(self) -> None:
        cutoff = time.monotonic() - self.retention_seconds
        with self._lock:
            removable = [
                record for record in self._records.values()
                if record.status != "running" and (record.ended_monotonic or 0) < cutoff
            ]
            completed = sorted(
                (record for record in self._records.values() if record.status != "running"),
                key=lambda record: record.ended_monotonic or 0,
            )
            overflow = max(0, len(self._records) - self.max_records)
            for record in {item.id: item for item in [*removable, *completed[:overflow]]}.values():
                self._records.pop(record.id, None)

    @staticmethod
    def _terminate_tree(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            try:
                completed = subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if completed.returncode != 0 and process.poll() is None:
                    process.kill()
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except (OSError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                process.kill()
