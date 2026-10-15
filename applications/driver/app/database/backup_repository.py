from __future__ import annotations

import sqlite3
import time
from typing import Any


def normalize_prefix(path: str) -> str:
    return (path or "").replace("\\", "/").strip("/")


def list_policies(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM backup_policies ORDER BY path_prefix COLLATE NOCASE").fetchall()
    return [dict(row) for row in rows]


def set_policy(conn: sqlite3.Connection, path_prefix: str, enabled: bool) -> dict[str, Any]:
    prefix = normalize_prefix(path_prefix)
    now = time.time()
    conn.execute(
        """INSERT INTO backup_policies(path_prefix, enabled, created_at, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(path_prefix) DO UPDATE SET enabled=excluded.enabled, updated_at=excluded.updated_at""",
        (prefix, int(enabled), now, now),
    )
    row = conn.execute("SELECT * FROM backup_policies WHERE path_prefix=?", (prefix,)).fetchone()
    return dict(row)


def delete_policy(conn: sqlite3.Connection, path_prefix: str) -> None:
    conn.execute("DELETE FROM backup_policies WHERE path_prefix=?", (normalize_prefix(path_prefix),))


def path_is_protected(conn: sqlite3.Connection, relative_path: str) -> bool:
    path = normalize_prefix(relative_path)
    rows = conn.execute("SELECT path_prefix FROM backup_policies WHERE enabled=1").fetchall()
    for row in rows:
        prefix = row["path_prefix"]
        if prefix == "" or path == prefix or path.startswith(prefix + "/"):
            return True
    return False
