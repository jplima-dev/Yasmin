from __future__ import annotations

import json
import os
import shutil
import threading
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_SETTINGS: dict[str, Any] = {
    "schema_version": 2,
    "revision": 0,
    "theme": "light",
    "accent": "#ff5b3d",
    "language": "pt-BR",
    "density": "comfortable",
    "font_size": "comfortable",
    "reduce_motion": False,
    "high_contrast": False,
    "decorations": True,
    "sidebar_collapsed": False,
    "dashboard_show_stats": True,
    "dashboard_show_health": True,
    "dashboard_card_size": "comfortable",
    "favorite_modules": ["organizer", "bridge", "photos"],
    "disabled_modules": [],
    "file_associations": {},
    "keyboard_shortcuts": {
        "search": "Ctrl+K",
        "terminal": "Ctrl+`",
        "dropzone": "Ctrl+Shift+O",
        "activities": "Ctrl+Shift+N",
    },
    "open_panel_on_start": False,
    "auto_start_modules": ["organizer", "bridge", "drive2"],
    "module_urls": {},
    "module_configs": {
        "bridge": {
            "host": "0.0.0.0", "port": 8876, "public_url": "",
            "discovery_port": 48765, "max_chunk_mb": 4,
            "data_dir": "", "received_dir": "", "tls_cert": "", "tls_key": "",
        },
        "drive2": {
            "run_local": True, "host": "127.0.0.1", "port": 8000, "storage_root": "data/files",
            "database": "drive2.db", "temp_root": "data/temp", "trash_root": "data/trash",
            "emails_root": "data/emails", "attachments_root": "data/attachments", "log_level": "INFO",
            "max_upload_mb": 1024, "sync_max_retries": 8,
            "scan_interval_seconds": 60, "sync_interval_seconds": 15,
            "tailscale_only": True, "auth_enabled": False,
            "auth_username": "admin", "auth_cookie_secure": False,
            "auth_session_hours": 24, "r2_enabled": False, "r2_region": "auto", "r2_prefix": "drive2",
            "gmail_enabled": False, "gmail_credentials_path": "config/gmail_credentials.json",
            "gmail_token_path": "config/gmail_token.json", "gmail_archive_after_days": 30,
            "gmail_max_message_mb": 50, "gmail_protect_starred": True,
            "gmail_protect_important": True, "gmail_trash_after_backup": False,
        },
    },
}

ALLOWED_VALUES = {
    "theme": {"light", "dark", "system"},
    "language": {"pt-BR", "en"},
    "density": {"compact", "comfortable", "spacious"},
    "font_size": {"small", "comfortable", "large"},
    "dashboard_card_size": {"compact", "comfortable", "wide"},
}

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
LEGACY_ACCENTS = {
    "purple": "#6750a4", "blue": "#1a73e8", "cyan": "#006a6a", "green": "#137333",
    "amber": "#b06000", "red": "#b3261e", "pink": "#a23b72", "mono": "#455a64",
}


def default_data_dir() -> Path:
    override = os.environ.get("WORKSPACE_OS_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "WorkspaceOS"
    return Path.home() / ".workspace-os"


class SettingsStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = (data_dir or default_data_dir()).resolve()
        self.path = self.data_dir / "settings.json"
        self.recovery_path = self.data_dir / "settings.last-invalid.json"
        self._lock = threading.RLock()
        self._last_load_issues: list[str] = []
        self._last_load_recovered = False

    def load(self) -> dict[str, Any]:
        with self._lock:
            current = deepcopy(DEFAULT_SETTINGS)
            self._last_load_issues = []
            self._last_load_recovered = False
            if not self.path.exists():
                return current
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except OSError as exc:
                self._record_load_issue(f"Não foi possível ler settings.json: {exc}")
                return current
            except json.JSONDecodeError as exc:
                self._record_load_issue(f"settings.json contém JSON inválido na linha {exc.lineno}.")
                return current
            if not isinstance(raw, dict):
                self._record_load_issue("settings.json precisa conter um objeto JSON.")
                return current

            raw = deepcopy(raw)
            schema_version = raw.get("schema_version", 1)
            if schema_version == 1:
                raw["schema_version"] = 2
                raw["accent"] = LEGACY_ACCENTS.get(str(raw.get("accent", "blue")), "#ff5b3d")
            elif schema_version != 2:
                self._record_load_issue(f"Versão de configuração incompatível: {schema_version!r}.")
                return current

            raw_configs = raw.get("module_configs")
            raw_driver = raw_configs.get("drive2") if isinstance(raw_configs, dict) else None
            if not isinstance(raw_driver, dict) or "run_local" not in raw_driver:
                if not isinstance(raw_configs, dict):
                    raw_configs = {}
                    raw["module_configs"] = raw_configs
                raw_configs.setdefault("drive2", {})["run_local"] = True
                auto_start = raw.setdefault("auto_start_modules", [])
                if isinstance(auto_start, list) and "drive2" not in auto_start:
                    auto_start.append("drive2")

            for key, value in raw.items():
                if key not in DEFAULT_SETTINGS:
                    self._record_load_issue(f"Configuração desconhecida ignorada: {key}.")
                    continue
                if key == "module_configs":
                    current["module_configs"] = self._recover_module_configs(value)
                    continue
                try:
                    current.update(self._validate({key: value}, partial=True))
                except ValueError as exc:
                    self._record_load_issue(f"{key}: {exc}")
            return current

    def load_status(self) -> dict[str, Any]:
        """Return non-sensitive recovery information for diagnostics and the Doctor."""
        with self._lock:
            self.load()
            return {
                "path": str(self.path),
                "exists": self.path.exists(),
                "valid": not self._last_load_issues,
                "recovered": self._last_load_recovered,
                "issues": list(self._last_load_issues),
                "recoveryBackup": str(self.recovery_path) if self.recovery_path.exists() else "",
            }

    def update(self, changes: dict[str, Any]) -> dict[str, Any]:
        validated = self._validate(changes, partial=True)
        with self._lock:
            current = self.load()
            preserve_invalid = self._last_load_recovered and self.path.is_file()
            current.update(validated)
            current["schema_version"] = 2
            current["revision"] = int(current.get("revision", 0)) + 1
            self.data_dir.mkdir(parents=True, exist_ok=True)
            if preserve_invalid:
                shutil.copy2(self.path, self.recovery_path)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(current, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
            self._last_load_issues = []
            self._last_load_recovered = False
            return current

    def _record_load_issue(self, message: str) -> None:
        self._last_load_issues.append(message)
        self._last_load_recovered = True

    def _recover_module_configs(self, value: object) -> dict[str, Any]:
        recovered = deepcopy(DEFAULT_SETTINGS["module_configs"])
        if not isinstance(value, dict):
            self._record_load_issue("module_configs precisa ser um objeto.")
            return recovered
        for module_id in set(value) - {"bridge", "drive2"}:
            self._record_load_issue(f"Configuração de módulo desconhecida ignorada: {module_id}.")
        validators = {
            "bridge": self._validate_bridge_config,
            "drive2": self._validate_driver_config,
        }
        for module_id, validator in validators.items():
            if module_id not in value:
                continue
            try:
                recovered[module_id] = validator(value[module_id])
            except ValueError as exc:
                self._record_load_issue(f"module_configs.{module_id}: {exc}")
        return recovered

    @staticmethod
    def _validate(values: dict[str, Any], *, partial: bool) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise ValueError("As configurações precisam ser um objeto JSON.")
        allowed = set(DEFAULT_SETTINGS)
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Configurações desconhecidas: {', '.join(sorted(unknown))}")
        result: dict[str, Any] = {}
        for key in ("theme", "language", "density", "font_size", "dashboard_card_size"):
            if key in values:
                if values[key] not in ALLOWED_VALUES[key]:
                    raise ValueError(f"Valor inválido para {key}.")
                result[key] = values[key]
        if "accent" in values:
            accent = values["accent"]
            if not isinstance(accent, str) or not HEX_COLOR.fullmatch(accent):
                raise ValueError("accent precisa ser uma cor hexadecimal no formato #RRGGBB.")
            result["accent"] = accent.lower()
        if "open_panel_on_start" in values:
            if not isinstance(values["open_panel_on_start"], bool):
                raise ValueError("open_panel_on_start precisa ser verdadeiro ou falso.")
            result["open_panel_on_start"] = values["open_panel_on_start"]
        for key in (
            "reduce_motion", "high_contrast", "decorations", "sidebar_collapsed",
            "dashboard_show_stats", "dashboard_show_health",
        ):
            if key in values:
                if not isinstance(values[key], bool):
                    raise ValueError(f"{key} precisa ser verdadeiro ou falso.")
                result[key] = values[key]
        if "auto_start_modules" in values:
            modules = values["auto_start_modules"]
            if not isinstance(modules, list) or not all(isinstance(item, str) for item in modules):
                raise ValueError("auto_start_modules precisa ser uma lista de IDs.")
            result["auto_start_modules"] = list(dict.fromkeys(modules))
        if "favorite_modules" in values:
            modules = values["favorite_modules"]
            if not isinstance(modules, list) or not all(isinstance(item, str) for item in modules):
                raise ValueError("favorite_modules precisa ser uma lista de IDs.")
            result["favorite_modules"] = list(dict.fromkeys(modules))
        if "disabled_modules" in values:
            modules = values["disabled_modules"]
            if not isinstance(modules, list) or not all(isinstance(item, str) for item in modules):
                raise ValueError("disabled_modules precisa ser uma lista de IDs.")
            result["disabled_modules"] = list(dict.fromkeys(modules))
        if "file_associations" in values:
            associations = values["file_associations"]
            if not isinstance(associations, dict) or not all(
                isinstance(extension, str) and re.fullmatch(r"[a-z0-9]{1,12}", extension)
                and isinstance(module_id, str) and re.fullmatch(r"[a-z][a-z0-9-]{1,39}", module_id)
                for extension, module_id in associations.items()
            ):
                raise ValueError("file_associations precisa relacionar extensões a IDs de módulos.")
            result["file_associations"] = associations
        if "keyboard_shortcuts" in values:
            shortcuts = values["keyboard_shortcuts"]
            allowed_shortcuts = set(DEFAULT_SETTINGS["keyboard_shortcuts"])
            if not isinstance(shortcuts, dict) or set(shortcuts) - allowed_shortcuts or not all(
                isinstance(value, str) and 1 <= len(value) <= 40 for value in shortcuts.values()
            ):
                raise ValueError("keyboard_shortcuts contém atalhos inválidos.")
            result["keyboard_shortcuts"] = {**DEFAULT_SETTINGS["keyboard_shortcuts"], **shortcuts}
        if "module_urls" in values:
            urls = values["module_urls"]
            if not isinstance(urls, dict) or not all(
                isinstance(key, str) and isinstance(value, str) for key, value in urls.items()
            ):
                raise ValueError("module_urls precisa relacionar IDs a endereços.")
            for value in urls.values():
                if value and not SettingsStore._valid_http_url(value):
                    raise ValueError("Endereços de módulos precisam usar http:// ou https://.")
            result["module_urls"] = urls
        if "module_configs" in values:
            configs = values["module_configs"]
            if not isinstance(configs, dict):
                raise ValueError("module_configs precisa ser um objeto.")
            unknown_modules = set(configs) - {"bridge", "drive2"}
            if unknown_modules:
                raise ValueError(f"Configuração de módulo desconhecida: {', '.join(sorted(unknown_modules))}")
            current = deepcopy(DEFAULT_SETTINGS["module_configs"])
            if "bridge" in configs:
                current["bridge"] = SettingsStore._validate_bridge_config(configs["bridge"])
            if "drive2" in configs:
                current["drive2"] = SettingsStore._validate_driver_config(configs["drive2"])
            result["module_configs"] = current
        if "schema_version" in values:
            if values["schema_version"] != 2:
                raise ValueError("Versão de configuração incompatível.")
            result["schema_version"] = 2
        if "revision" in values:
            if not isinstance(values["revision"], int) or values["revision"] < 0:
                raise ValueError("revision precisa ser um inteiro não negativo.")
            result["revision"] = values["revision"]
        if not partial:
            missing = allowed - set(values)
            if missing:
                raise ValueError(f"Configurações ausentes: {', '.join(sorted(missing))}")
        return result

    @staticmethod
    def _validate_bridge_config(value: object) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("A configuração do Bridge precisa ser um objeto.")
        allowed = set(DEFAULT_SETTINGS["module_configs"]["bridge"])
        if set(value) - allowed:
            raise ValueError("A configuração do Bridge contém campos desconhecidos.")
        merged = {**DEFAULT_SETTINGS["module_configs"]["bridge"], **value}
        host = str(merged["host"]).strip()
        if not host or len(host) > 255:
            raise ValueError("Host do Bridge inválido.")
        port = SettingsStore._port(merged["port"], "Bridge")
        discovery_port = SettingsStore._port(merged["discovery_port"], "descoberta do Bridge")
        max_chunk_mb = SettingsStore._integer(merged["max_chunk_mb"], 1, 64, "Bloco do Bridge")
        public_url = str(merged["public_url"]).strip().rstrip("/")
        if public_url:
            if not SettingsStore._valid_http_url(public_url):
                raise ValueError("URL pública do Bridge inválida.")
        tls_cert = str(merged["tls_cert"]).strip()
        tls_key = str(merged["tls_key"]).strip()
        if bool(tls_cert) != bool(tls_key):
            raise ValueError("Informe certificado e chave TLS do Bridge juntos.")
        return {
            "host": host, "port": port, "public_url": public_url,
            "discovery_port": discovery_port, "max_chunk_mb": max_chunk_mb,
            "data_dir": str(merged["data_dir"]).strip(),
            "received_dir": str(merged["received_dir"]).strip(),
            "tls_cert": tls_cert, "tls_key": tls_key,
        }

    @staticmethod
    def _validate_driver_config(value: object) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("A configuração do InkDriver precisa ser um objeto.")
        allowed = set(DEFAULT_SETTINGS["module_configs"]["drive2"])
        if set(value) - allowed:
            raise ValueError("A configuração do InkDriver contém campos desconhecidos.")
        merged = {**DEFAULT_SETTINGS["module_configs"]["drive2"], **value}
        booleans = (
            "run_local", "tailscale_only", "auth_enabled", "auth_cookie_secure", "r2_enabled", "gmail_enabled",
            "gmail_protect_starred", "gmail_protect_important", "gmail_trash_after_backup",
        )
        if any(not isinstance(merged[key], bool) for key in booleans):
            raise ValueError("As opções do InkDriver precisam ser verdadeiras ou falsas.")
        log_level = str(merged["log_level"]).strip().upper() or "INFO"
        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Nível de log do InkDriver inválido.")
        return {
            "run_local": merged["run_local"],
            "host": str(merged["host"]).strip() or "0.0.0.0",
            "port": SettingsStore._port(merged["port"], "InkDriver"),
            "storage_root": str(merged["storage_root"]).strip() or "data/files",
            "database": str(merged["database"]).strip() or "drive2.db",
            "temp_root": str(merged["temp_root"]).strip() or "data/temp",
            "trash_root": str(merged["trash_root"]).strip() or "data/trash",
            "emails_root": str(merged["emails_root"]).strip() or "data/emails",
            "attachments_root": str(merged["attachments_root"]).strip() or "data/attachments",
            "log_level": log_level,
            "max_upload_mb": SettingsStore._integer(merged["max_upload_mb"], 1, 102400, "Upload máximo"),
            "sync_max_retries": SettingsStore._integer(merged["sync_max_retries"], 1, 100, "Tentativas de sincronização"),
            "scan_interval_seconds": SettingsStore._integer(merged["scan_interval_seconds"], 15, 86400, "Intervalo de varredura"),
            "sync_interval_seconds": SettingsStore._integer(merged["sync_interval_seconds"], 5, 86400, "Intervalo de sincronização"),
            "tailscale_only": merged["tailscale_only"], "auth_enabled": merged["auth_enabled"],
            "auth_username": str(merged["auth_username"]).strip() or "admin",
            "auth_cookie_secure": merged["auth_cookie_secure"],
            "auth_session_hours": SettingsStore._integer(merged["auth_session_hours"], 1, 720, "Duração da sessão"),
            "r2_enabled": merged["r2_enabled"],
            "r2_region": str(merged["r2_region"]).strip() or "auto",
            "r2_prefix": str(merged["r2_prefix"]).strip().strip("/") or "drive2",
            "gmail_enabled": merged["gmail_enabled"],
            "gmail_credentials_path": str(merged["gmail_credentials_path"]).strip() or "config/gmail_credentials.json",
            "gmail_token_path": str(merged["gmail_token_path"]).strip() or "config/gmail_token.json",
            "gmail_archive_after_days": SettingsStore._integer(merged["gmail_archive_after_days"], 1, 3650, "Idade para arquivar Gmail"),
            "gmail_max_message_mb": SettingsStore._integer(merged["gmail_max_message_mb"], 1, 1024, "Tamanho máximo do Gmail"),
            "gmail_protect_starred": merged["gmail_protect_starred"],
            "gmail_protect_important": merged["gmail_protect_important"],
            "gmail_trash_after_backup": merged["gmail_trash_after_backup"],
        }

    @staticmethod
    def _integer(value: object, minimum: int, maximum: int, label: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{label} inválido.")
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} inválido.") from exc
        if not minimum <= number <= maximum:
            raise ValueError(f"{label} precisa ficar entre {minimum} e {maximum}.")
        return number

    @staticmethod
    def _port(value: object, label: str) -> int:
        return SettingsStore._integer(value, 1, 65535, f"Porta do {label}")

    @staticmethod
    def _valid_http_url(value: str) -> bool:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        try:
            port = parsed.port
        except ValueError:
            return False
        return port is None or 1 <= port <= 65535


def effective_module_urls(settings: dict[str, Any]) -> dict[str, str]:
    """Resolve URLs locais configuráveis sem apagar endereços remotos salvos."""
    urls = dict(settings.get("module_urls") or {})
    driver = (settings.get("module_configs") or {}).get("drive2") or {}
    if driver.get("run_local", True):
        port = SettingsStore._port(driver.get("port", 8000), "InkDriver")
        urls["drive2"] = f"http://127.0.0.1:{port}"
    return urls
