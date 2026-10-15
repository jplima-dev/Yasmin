from __future__ import annotations

import sqlite3
import time
from typing import Any


def add_trash(conn: sqlite3.Connection, original_path: str, trash_path: str, is_directory: bool) -> int:
    cur = conn.execute(
        "INSERT INTO trash_entries(original_path,trash_path,is_directory,deleted_at) VALUES(?,?,?,?)",
        (original_path, trash_path, int(is_directory), time.time()),
    )
    return int(cur.lastrowid)


def list_trash(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM trash_entries ORDER BY deleted_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def get_trash(conn: sqlite3.Connection, entry_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM trash_entries WHERE id=?", (entry_id,)).fetchone()
    return dict(row) if row else None


def delete_trash(conn: sqlite3.Connection, entry_id: int) -> None:
    conn.execute("DELETE FROM trash_entries WHERE id=?", (entry_id,))
