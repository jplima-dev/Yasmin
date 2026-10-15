from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from .activity import ActivityStore
from .clipboard import ClipboardStore
from .dropzone import DropzoneStore
from .presets import PresetStore
from .registry import MODULE_ID, ModuleDefinition, ModuleRegistry
from .settings import SettingsStore


PORTABLE_FORMAT = "ink-workspace-portable"
PORTABLE_VERSION = 1
MAX_PORTABLE_BYTES = 512 * 1024 * 1024
MAX_PORTABLE_UNCOMPRESSED_BYTES = 1024 * 1024 * 1024
MAX_PORTABLE_MANIFEST_BYTES = 16 * 1024 * 1024
REPOSITORY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


class ModuleDataStore:
    """Snapshots explicitly published by modules through the public Core API."""

    def __init__(self, data_dir: Path) -> None:
        self.root = (data_dir / "module-data").resolve()
        self._lock = threading.RLock()

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            if not self.root.exists():
                return []
            result = []
            for path in sorted(self.root.glob("*.json")):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                result.append({
                    "moduleId": payload.get("moduleId", path.stem),
                    "updatedAt": payload.get("updatedAt", ""),
                    "size": path.stat().st_size,
                    "schemaVersion": payload.get("schemaVersion", 1),
                })
            return result

    def get(self, module_id: str) -> dict[str, Any] | None:
        self._validate_id(module_id)
        path = self.root / f"{module_id}.json"
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def save(self, module_id: str, payload: object) -> dict[str, Any]:
        self._validate_id(module_id)
        if not isinstance(payload, dict):
            raise ValueError("Os dados do módulo precisam ser um objeto JSON.")
        data = payload.get("data")
        try:
            serialized = json.dumps(data, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("Os dados do módulo precisam ser compatíveis com JSON.") from exc
        if len(serialized.encode("utf-8")) > 8 * 1024 * 1024:
            raise ValueError("O snapshot do módulo excede 8 MiB.")
        snapshot = {
            "moduleId": module_id,
            "schemaVersion": max(1, int(payload.get("schemaVersion", 1))),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            path = self.root / f"{module_id}.json"
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)
        return {key: snapshot[key] for key in ("moduleId", "schemaVersion", "updatedAt")}

    @staticmethod
    def _validate_id(module_id: str) -> None:
        if not MODULE_ID.fullmatch(module_id):
            raise ValueError("ID de módulo inválido.")


class PortableArchive:
    def __init__(
        self,
        settings: SettingsStore,
        activity: ActivityStore,
        presets: PresetStore,
        clipboard: ClipboardStore,
        dropzone: DropzoneStore,
        module_data: ModuleDataStore,
        ecosystem_root: Path,
    ) -> None:
        self.settings = settings
        self.activity = activity
        self.presets = presets
        self.clipboard = clipboard
        self.dropzone = dropzone
        self.module_data = module_data
        self.ecosystem_root = ecosystem_root.resolve()

    def export(self, sections: set[str]) -> bytes:
        allowed = {"settings", "presets", "clipboard", "activity", "files", "modules"}
        sections &= allowed
        if not sections:
            sections = allowed
        payload: dict[str, Any] = {
            "format": PORTABLE_FORMAT,
            "version": PORTABLE_VERSION,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "sections": sorted(sections),
            "sourceRoot": str(self.ecosystem_root),
        }
        if "settings" in sections:
            payload["settings"] = self.settings.load()
        if "presets" in sections:
            payload["presets"] = self.presets.list()
        if "clipboard" in sections:
            payload["clipboard"] = self.clipboard.list()
        if "activity" in sections:
            payload["activity"] = self.activity.list(limit=250)
        if "modules" in sections:
            payload["moduleData"] = [snapshot for item in self.module_data.list() if (snapshot := self.module_data.get(item["moduleId"]))]
        if "files" in sections:
            payload["dropzone"] = self.dropzone.history()
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("workspace-backup.json", json.dumps(payload, ensure_ascii=False, indent=2))
            if "files" in sections:
                for item in self.dropzone.history():
                    try:
                        record, path = self.dropzone.get(str(item.get("id", "")))
                    except KeyError:
                        continue
                    if path:
                        archive.write(path, f"files/{record['id']}.bin")
        return output.getvalue()

    def inspect(self, content: bytes) -> dict[str, Any]:
        payload, _ = self._read(content)
        return {
            "format": payload["format"],
            "version": payload["version"],
            "createdAt": payload.get("createdAt", ""),
            "sections": payload.get("sections", []),
            "counts": {
                "presets": len(payload.get("presets", [])),
                "clipboard": len(payload.get("clipboard", [])),
                "activity": len(payload.get("activity", [])),
                "files": len(payload.get("dropzone", [])),
                "modules": len(payload.get("moduleData", [])),
            },
        }

    def restore(self, content: bytes, sections: set[str]) -> dict[str, Any]:
        payload, archive = self._read(content)
        available = set(payload.get("sections", []))
        chosen = (sections & available) if sections else available
        restored: dict[str, int] = {}
        if "settings" in chosen and isinstance(payload.get("settings"), dict):
            settings = dict(payload["settings"])
            settings.pop("revision", None)
            self.settings.update(settings)
            restored["settings"] = 1
        if "presets" in chosen:
            restored["presets"] = self._restore_items(payload.get("presets"), self.presets.save)
        if "clipboard" in chosen:
            restored["clipboard"] = self._restore_items(payload.get("clipboard"), self.clipboard.add)
        if "activity" in chosen:
            restored["activity"] = self._restore_items(reversed(payload.get("activity", [])), self.activity.add)
        if "modules" in chosen:
            count = 0
            for item in payload.get("moduleData", []):
                if isinstance(item, dict) and MODULE_ID.fullmatch(str(item.get("moduleId", ""))):
                    self.module_data.save(str(item["moduleId"]), item)
                    count += 1
            restored["modules"] = count
        if "files" in chosen:
            count = 0
            for item in payload.get("dropzone", []):
                if not isinstance(item, dict) or item.get("kind") != "file":
                    continue
                member = f"files/{item.get('id', '')}.bin"
                try:
                    blob = archive.read(member)
                except KeyError:
                    continue
                self.dropzone.add(
                    name=str(item.get("name", "arquivo")), mime=str(item.get("type", "application/octet-stream")),
                    content=blob, last_modified=int(item.get("lastModified", 0) or 0),
                )
                count += 1
            restored["files"] = count
        archive.close()
        source_root = str(payload.get("sourceRoot", ""))
        return {
            "ok": True, "restored": restored,
            "relocated": bool(source_root and Path(source_root) != self.ecosystem_root),
            "sourceRoot": source_root,
            "currentRoot": str(self.ecosystem_root),
            "pathWarnings": _missing_paths(payload.get("settings", {})) if "settings" in chosen else [],
        }

    @staticmethod
    def _restore_items(items: object, callback: Any) -> int:
        count = 0
        if not isinstance(items, (list, tuple)) and not hasattr(items, "__iter__"):
            return count
        for item in items:
            if not isinstance(item, dict):
                continue
            safe = {key: value for key, value in item.items() if key not in {"id", "createdAt", "updatedAt", "read"}}
            try:
                callback(safe)
                count += 1
            except (ValueError, KeyError):
                continue
        return count

    @staticmethod
    def _read(content: bytes) -> tuple[dict[str, Any], zipfile.ZipFile]:
        if len(content) > MAX_PORTABLE_BYTES:
            raise ValueError("O arquivo portátil excede 512 MiB.")
        try:
            archive = zipfile.ZipFile(io.BytesIO(content), "r")
            infos = archive.infolist()
            names = [item.filename for item in infos]
            normalized_paths = [PurePosixPath(name.replace("\\", "/")) for name in names]
            if len(names) > 1000 or len(set(names)) != len(names) or any(
                name.startswith(("/", "\\"))
                or ".." in normalized.parts
                or (normalized.parts and normalized.parts[0].endswith(":"))
                for name, normalized in zip(names, normalized_paths)
            ):
                raise ValueError("O pacote contém caminhos inválidos.")
            if any(item.flag_bits & 0x1 for item in infos):
                raise ValueError("Pacotes criptografados não são aceitos.")
            if sum(item.file_size for item in infos) > MAX_PORTABLE_UNCOMPRESSED_BYTES:
                raise ValueError("O pacote expandido excede 1 GiB.")
            manifest = archive.getinfo("workspace-backup.json")
            if manifest.file_size > MAX_PORTABLE_MANIFEST_BYTES:
                raise ValueError("O índice do pacote excede 16 MiB.")
            payload = json.loads(archive.read("workspace-backup.json"))
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
            raise ValueError("Pacote portátil inválido.") from exc
        if payload.get("format") != PORTABLE_FORMAT or payload.get("version") != PORTABLE_VERSION:
            archive.close()
            raise ValueError("Versão de pacote portátil incompatível.")
        return payload, archive


class GitProjects:
    def __init__(self, ecosystem_root: Path) -> None:
        self.ecosystem_root = ecosystem_root.resolve()

    def status(self, module: ModuleDefinition, *, fetch: bool = False) -> dict[str, Any]:
        path = module.project_path
        if not path or not (path / ".git").exists():
            return {"available": False, "moduleId": module.id}
        if fetch:
            self._run(path, ["fetch", "--prune"], timeout=60)
        branch = self._run(path, ["branch", "--show-current"], check=False)["stdout"].strip() or "detached"
        dirty = bool(self._run(path, ["status", "--porcelain"], check=False)["stdout"].strip())
        remote = self._run(path, ["remote", "get-url", "origin"], check=False)["stdout"].strip()
        upstream = self._run(path, ["rev-parse", "--abbrev-ref", "@{upstream}"], check=False)
        ahead = behind = 0
        if upstream["ok"]:
            counts = self._run(path, ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"], check=False)["stdout"].split()
            if len(counts) == 2:
                ahead, behind = (int(value) for value in counts)
        return {
            "available": True, "moduleId": module.id, "branch": branch, "dirty": dirty,
            "remote": remote, "upstream": upstream["stdout"].strip() if upstream["ok"] else "",
            "ahead": ahead, "behind": behind,
        }

    def update(self, module: ModuleDefinition) -> dict[str, Any]:
        status = self.status(module, fetch=True)
        if not status.get("available"):
            raise ValueError("Este módulo não possui um repositório Git.")
        if status.get("dirty"):
            raise ValueError("O módulo possui alterações locais. Revise ou faça commit antes de atualizar.")
        if not status.get("upstream"):
            raise ValueError("O branch atual não possui upstream configurado.")
        if not status.get("behind"):
            return {"ok": True, "message": "O módulo já está atualizado.", "status": status}
        result = self._run(module.project_path, ["pull", "--ff-only"], timeout=120)
        return {"ok": True, "message": result["stdout"].strip() or "Atualização concluída.", "status": self.status(module)}

    def revision(self, module: ModuleDefinition) -> str:
        if not module.project_path or not (module.project_path / ".git").exists():
            raise ValueError("Este módulo não possui um repositório Git.")
        return self._run(module.project_path, ["rev-parse", "HEAD"])["stdout"].strip()

    def rollback(self, module: ModuleDefinition, revision: str) -> dict[str, Any]:
        if not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
            raise ValueError("Revisão de rollback inválida.")
        if not module.project_path:
            raise ValueError("Pasta do módulo indisponível.")
        result = self._run(module.project_path, ["reset", "--hard", revision], timeout=60)
        return {"ok": True, "revision": revision, "message": result["stdout"].strip() or "Rollback concluído."}

    def install(self, payload: dict[str, Any]) -> dict[str, Any]:
        source_type = str(payload.get("type", "folder"))
        if source_type == "folder":
            raw_path = str(payload.get("path", "")).strip()
            if len(raw_path) >= 2 and raw_path[0] == raw_path[-1] and raw_path[0] in {'"', "'"}:
                raw_path = raw_path[1:-1].strip()
            folder = Path(raw_path).expanduser().resolve()
            try:
                folder.relative_to(self.ecosystem_root)
            except ValueError as exc:
                raise ValueError("A pasta precisa estar dentro do ecossistema Ink.") from exc
            if folder.parent != self.ecosystem_root or not folder.is_dir():
                raise ValueError("Escolha uma pasta direta do ecossistema.")
            activated = self._activate_pending_manifest(folder)
            generated = self._ensure_manifest(folder)
            if not (folder / "ink-module.json").is_file():
                raise ValueError(
                    "A pasta não contém ink-module.json nem uma página web estática (index.html ou web/index.html)."
                )
            message = "Pasta registrada. Recarregue os módulos."
            if activated:
                message = "Manifesto pendente ativado e pasta registrada. Recarregue os módulos."
            elif generated:
                message = "Manifesto mínimo criado e pasta registrada. Recarregue os módulos."
            return {"ok": True, "path": str(folder), "message": message}
        if source_type != "git":
            raise ValueError("Tipo de instalação inválido.")
        repository = str(payload.get("repository", "")).strip()
        parsed = urlparse(repository)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise ValueError("Use um endereço HTTP ou HTTPS de repositório Git.")
        name = str(payload.get("name", "")).strip() or Path(parsed.path).stem.removesuffix(".git")
        if not REPOSITORY_NAME.fullmatch(name):
            raise ValueError("Nome da pasta do módulo inválido.")
        destination = (self.ecosystem_root / name).resolve()
        if destination.exists():
            raise ValueError("Já existe uma pasta com esse nome.")
        executable = shutil.which("git.exe") or shutil.which("git")
        if not executable:
            raise RuntimeError("Git não foi encontrado.")
        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        try:
            completed = subprocess.run(
                [executable, "clone", "--depth", "1", repository, str(destination)],
                cwd=self.ecosystem_root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), env=environment,
            )
        except subprocess.TimeoutExpired as exc:
            if destination.exists():
                shutil.rmtree(destination, ignore_errors=True)
            raise RuntimeError("O clone do repositório demorou mais de 3 minutos e foi cancelado.") from exc
        if completed.returncode:
            if destination.exists():
                shutil.rmtree(destination, ignore_errors=True)
            raise RuntimeError(completed.stderr.strip() or "Falha ao clonar o repositório.")
        activated = self._activate_pending_manifest(destination)
        generated = self._ensure_manifest(destination)
        if not (destination / "ink-module.json").is_file():
            shutil.rmtree(destination, ignore_errors=True)
            raise ValueError(
                "O repositório não contém ink-module.json nem uma página web estática (index.html ou web/index.html)."
            )
        message = "Repositório instalado. Recarregue os módulos."
        if activated:
            message = "Repositório instalado com manifesto pendente ativado. Recarregue os módulos."
        elif generated:
            message = "Repositório instalado com manifesto mínimo. Recarregue os módulos."
        return {"ok": True, "path": str(destination), "message": message}

    @staticmethod
    def _activate_pending_manifest(folder: Path) -> bool:
        """Activate a reviewed manifest only when the user installs its folder."""
        manifest = folder / "ink-module.json"
        pending = folder / "ink-module.json.pending"
        if not pending.is_file():
            return False
        if manifest.exists():
            raise ValueError("A pasta possui manifestos ativo e pendente; mantenha apenas um deles.")
        try:
            payload = json.loads(pending.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("O manifesto pendente contém JSON inválido.") from exc
        if not isinstance(payload, dict):
            raise ValueError("O manifesto pendente precisa conter um objeto JSON.")
        pending.replace(manifest)
        return True

    @staticmethod
    def _ensure_manifest(folder: Path) -> bool:
        """Create a safe, passive manifest for a legacy static web module."""
        manifest = folder / "ink-module.json"
        if manifest.is_file():
            return False
        entry_file = next((item for item in ("index.html", "web/index.html") if (folder / item).is_file()), None)
        if not entry_file:
            return False
        module_id = re.sub(r"[^a-z0-9]+", "-", folder.name.lower()).strip("-")
        if not module_id or not module_id[0].isalpha():
            module_id = f"ink-{module_id}" if module_id else "ink-module"
        module_id = module_id[:40].rstrip("-")
        if len(module_id) < 2:
            module_id = "ink-module"
        display_name = re.sub(r"[-_]+", " ", folder.name).strip().title() or "Módulo Ink"
        manifest.write_text(json.dumps({
            "id": module_id,
            "name": display_name,
            "description": "Módulo web estático do ecossistema Ink.",
            "category": "utilities",
            "kind": "static-web",
            "entryFile": entry_file,
            "icon": "app",
            "version": "0.1.0",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return True

    def _run(self, path: Path, arguments: list[str], *, check: bool = True, timeout: int = 20) -> dict[str, Any]:
        executable = shutil.which("git.exe") or shutil.which("git")
        if not executable:
            raise RuntimeError("Git não foi encontrado.")
        completed = subprocess.run(
            [executable, "-c", f"safe.directory={path}", *arguments], cwd=path,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if check and completed.returncode:
            raise RuntimeError(completed.stderr.strip() or "O comando Git falhou.")
        return {"ok": completed.returncode == 0, "stdout": completed.stdout, "stderr": completed.stderr}


def module_audit(registry: ModuleRegistry, processes: Any, custom_urls: dict[str, str] | None = None) -> dict[str, Any]:
    custom_urls = custom_urls or {}
    ports: dict[int, list[str]] = {}
    rows = []
    for module in registry.modules.values():
        issues: list[dict[str, str]] = []
        effective_url = custom_urls.get(module.id)
        for url in (effective_url or module.service_url or module.url, effective_url or module.health_url):
            if not url:
                continue
            parsed = urlparse(url)
            try:
                port = parsed.port or (443 if parsed.scheme == "https" else 80)
            except ValueError:
                issues.append({
                    "code": "INVALID_URL", "level": "error", "message": f"URL inválida: {url}",
                    "probableCause": "A URL possui uma porta fora da faixa válida.",
                    "recoveryAction": "Corrija a URL no manifesto ou nas configurações do módulo.",
                })
                continue
            ports.setdefault(port, []).append(module.id)
        if module.project_path and not module.project_path.exists():
            issues.append({
                "code": "MODULE_PATH_MISSING", "level": "error", "message": "Pasta do módulo ausente.",
                "probableCause": "A pasta foi movida, renomeada ou não está sincronizada.",
                "recoveryAction": "Restaure a pasta ao lado do Workspace OS ou reinstale o módulo.",
            })
        if module.entry_file and module.project_path and not (module.project_path / module.entry_file).is_file():
            issues.append({
                "code": "ENTRY_FILE_MISSING", "level": "error", "message": f"Arquivo inicial ausente: {module.entry_file}",
                "probableCause": "O build está incompleto ou entryFile não corresponde à estrutura atual.",
                "recoveryAction": "Gere novamente o build ou corrija entryFile no ink-module.json.",
            })
        if module.command and not Path(module.command[0]).is_absolute() and not module.command[0].startswith("{") and not shutil.which(module.command[0]):
            issues.append({
                "code": "EXECUTABLE_MISSING", "level": "error", "message": f"Dependência não encontrada: {module.command[0]}",
                "probableCause": "O executável não está instalado ou não aparece no PATH.",
                "recoveryAction": f"Instale {module.command[0]} ou ajuste o comando no manifesto.",
            })
        size = _folder_size(module.project_path) if module.project_path and module.project_path.exists() else 0
        digest = ""
        if module.entry_file and module.project_path:
            entry = module.project_path / module.entry_file
            if entry.is_file():
                digest = hashlib.sha256(entry.read_bytes()).hexdigest()[:16]
        rows.append({
            "id": module.id, "name": module.name, "issues": issues, "size": size, "integrity": digest,
            "managedState": processes.managed_state(module.id), "source": module.source, "version": module.version,
        })
    conflicts = []
    for port, ids in ports.items():
        unique = list(dict.fromkeys(ids))
        if len(unique) > 1:
            conflicts.append({"port": port, "modules": unique})
            for row in rows:
                if row["id"] in unique:
                    row["issues"].append({
                        "code": "PORT_CONFLICT", "level": "warning",
                        "message": f"Porta {port} também usada por {', '.join(item for item in unique if item != row['id'])}.",
                        "probableCause": "Dois serviços foram configurados com a mesma porta local.",
                        "recoveryAction": "Escolha portas distintas nas configurações dos módulos e reinicie os serviços.",
                    })
    return {"modules": rows, "portConflicts": conflicts, "manifestErrors": registry.discovery_errors}


def _folder_size(root: Path | None, *, limit: int = 20_000) -> int:
    if not root:
        return 0
    total = count = 0
    ignored = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
    for current, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name not in ignored]
        for name in files:
            count += 1
            if count > limit:
                return total
            try:
                total += (Path(current) / name).stat().st_size
            except OSError:
                continue
    return total


def _missing_paths(value: object, prefix: str = "settings") -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            warnings.extend(_missing_paths(item, f"{prefix}.{key}"))
    elif isinstance(value, str) and value and (Path(value).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", value)):
        if not Path(value).exists():
            warnings.append({"setting": prefix, "path": value})
    return warnings[:100]
