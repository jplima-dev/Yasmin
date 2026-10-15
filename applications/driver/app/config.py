from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _resolve_path(value: str | None, default: str) -> Path:
    raw = Path(value or default).expanduser()
    if not raw.is_absolute():
        raw = PROJECT_ROOT / raw
    return raw.resolve()


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    version: str = "1.0.0"
    host: str = os.getenv("DRIVE2_HOST", "0.0.0.0")
    port: int = int(os.getenv("DRIVE2_PORT", "8000"))
    storage_root: Path = _resolve_path(os.getenv("DRIVE2_STORAGE_ROOT"), "data/files")
    database_path: Path = _resolve_path(os.getenv("DRIVE2_DATABASE"), "drive2.db")
    temp_root: Path = _resolve_path(os.getenv("DRIVE2_TEMP_ROOT"), "data/temp")
    trash_root: Path = _resolve_path(os.getenv("DRIVE2_TRASH_ROOT"), "data/trash")
    emails_root: Path = _resolve_path(os.getenv("DRIVE2_EMAILS_ROOT"), "data/emails")
    attachments_root: Path = _resolve_path(os.getenv("DRIVE2_ATTACHMENTS_ROOT"), "data/attachments")
    log_level: str = os.getenv("DRIVE2_LOG_LEVEL", "INFO").upper()
    max_upload_mb: int = int(os.getenv("DRIVE2_MAX_UPLOAD_MB", "1024"))
    scan_interval_seconds: int = max(15, int(os.getenv("DRIVE2_SCAN_INTERVAL_SECONDS", "60")))
    sync_interval_seconds: int = max(5, int(os.getenv("DRIVE2_SYNC_INTERVAL_SECONDS", "15")))
    sync_max_retries: int = max(1, int(os.getenv("DRIVE2_SYNC_MAX_RETRIES", "8")))

    tailscale_only: bool = _bool("DRIVE2_TAILSCALE_ONLY", True)

    auth_enabled: bool = _bool("DRIVE2_AUTH_ENABLED", False)
    auth_username: str = os.getenv("DRIVE2_AUTH_USERNAME", "admin")
    auth_password_hash: str = os.getenv("DRIVE2_AUTH_PASSWORD_HASH", "")
    auth_secret: str = os.getenv("DRIVE2_AUTH_SECRET", "")
    auth_cookie_secure: bool = _bool("DRIVE2_AUTH_COOKIE_SECURE", False)
    auth_session_hours: int = max(1, int(os.getenv("DRIVE2_AUTH_SESSION_HOURS", "24")))

    r2_enabled: bool = _bool("R2_ENABLED", False)
    r2_account_id: str = os.getenv("R2_ACCOUNT_ID", "")
    r2_access_key_id: str = os.getenv("R2_ACCESS_KEY_ID", "")
    r2_secret_access_key: str = os.getenv("R2_SECRET_ACCESS_KEY", "")
    r2_bucket: str = os.getenv("R2_BUCKET", "")
    r2_endpoint: str = os.getenv("R2_ENDPOINT", "")
    r2_region: str = os.getenv("R2_REGION", "auto")
    r2_prefix: str = os.getenv("R2_PREFIX", "drive2").strip("/")

    gmail_enabled: bool = _bool("GMAIL_ENABLED", False)
    gmail_credentials_path: Path = _resolve_path(os.getenv("GMAIL_CREDENTIALS_PATH"), "config/gmail_credentials.json")
    gmail_token_path: Path = _resolve_path(os.getenv("GMAIL_TOKEN_PATH"), "config/gmail_token.json")
    gmail_archive_after_days: int = max(1, int(os.getenv("GMAIL_ARCHIVE_AFTER_DAYS", "30")))
    gmail_max_message_mb: int = max(1, int(os.getenv("GMAIL_MAX_MESSAGE_MB", "50")))
    gmail_protect_starred: bool = _bool("GMAIL_PROTECT_STARRED", True)
    gmail_protect_important: bool = _bool("GMAIL_PROTECT_IMPORTANT", True)
    gmail_trash_after_backup: bool = _bool("GMAIL_TRASH_AFTER_BACKUP", False)


settings = Settings()
