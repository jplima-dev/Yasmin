from __future__ import annotations

import sqlite3
import time
from typing import Any


def add_log(conn: sqlite3.Connection, level: str, event: str, message: str = "") -> None:
    conn.execute(
        "INSERT INTO logs(level,event,message,created_at) VALUES(?,?,?,?)",
        (level.upper(), event, message[:4000], time.time()),
    )


def list_logs(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM logs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]
