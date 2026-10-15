from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import settings

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    relative_path TEXT NOT NULL UNIQUE,
    parent_path TEXT NOT NULL DEFAULT '',
    is_directory INTEGER NOT NULL DEFAULT 0,
    size INTEGER NOT NULL DEFAULT 0,
    mime_type TEXT,
    sha256 TEXT,
    created_at REAL,
    modified_at REAL,
    indexed_at REAL NOT NULL,
    last_seen_at REAL,
    local_available INTEGER NOT NULL DEFAULT 1,
    cloud_available INTEGER NOT NULL DEFAULT 0,
    sync_status TEXT NOT NULL DEFAULT 'LOCAL_ONLY',
    last_backup REAL,
    cloud_key TEXT,
    favorite INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_parent ON files(parent_path);
CREATE INDEX IF NOT EXISTS idx_files_name ON files(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_files_modified ON files(modified_at DESC);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(sync_status);

CREATE TABLE IF NOT EXISTS directories (
    relative_path TEXT PRIMARY KEY,
    discovered_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS backup_policies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path_prefix TEXT NOT NULL UNIQUE,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    operation TEXT NOT NULL DEFAULT 'UPLOAD',
    status TEXT NOT NULL DEFAULT 'WAITING_BACKUP',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at REAL NOT NULL,
    last_error TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(file_id, operation),
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sync_queue_due ON sync_queue(status, next_attempt_at);

CREATE TABLE IF NOT EXISTS sync_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER,
    relative_path TEXT NOT NULL,
    operation TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT,
    started_at REAL NOT NULL,
    finished_at REAL,
    FOREIGN KEY(file_id) REFERENCES files(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_sync_history_time ON sync_history(started_at DESC);

CREATE TABLE IF NOT EXISTS trash_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_path TEXT NOT NULL,
    trash_path TEXT NOT NULL UNIQUE,
    is_directory INTEGER NOT NULL,
    deleted_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS email_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_message_id TEXT NOT NULL UNIQUE,
    thread_id TEXT,
    sender TEXT,
    recipients TEXT,
    subject TEXT,
    message_date REAL,
    internal_date REAL,
    label_ids TEXT NOT NULL DEFAULT '[]',
    eml_path TEXT NOT NULL,
    eml_sha256 TEXT NOT NULL,
    size INTEGER NOT NULL DEFAULT 0,
    backed_up INTEGER NOT NULL DEFAULT 0,
    trashed_in_gmail INTEGER NOT NULL DEFAULT 0,
    archived_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_email_date ON email_messages(message_date DESC);

CREATE TABLE IF NOT EXISTS email_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    mime_type TEXT,
    size INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL,
    FOREIGN KEY(email_id) REFERENCES email_messages(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    event TEXT NOT NULL,
    message TEXT,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_logs_created ON logs(created_at DESC);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    target = db_path or settings.database_path
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _ensure_columns(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(files)")}
    additions = {
        "sha256": "TEXT",
        "last_seen_at": "REAL",
        "favorite": "INTEGER NOT NULL DEFAULT 0",
        "error_message": "TEXT",
    }
    for name, definition in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE files ADD COLUMN {name} {definition}")


def init_db(db_path: Path | None = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        _ensure_columns(conn)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_favorite ON files(favorite)")
        conn.commit()


@contextmanager
def db_session(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
