from __future__ import annotations

import sqlite3
import time
from typing import Any


def enqueue(conn: sqlite3.Connection, file_id: int, operation: str = "UPLOAD") -> None:
    now = time.time()
    conn.execute(
        """
        INSERT INTO sync_queue(file_id, operation, status, attempts, next_attempt_at, created_at, updated_at)
        VALUES (?, ?, 'WAITING_BACKUP', 0, ?, ?, ?)
        ON CONFLICT(file_id, operation) DO UPDATE SET
            status='WAITING_BACKUP', next_attempt_at=excluded.next_attempt_at,
            updated_at=excluded.updated_at, last_error=NULL
        """,
        (file_id, operation, now, now, now),
    )
    conn.execute("UPDATE files SET sync_status='WAITING_BACKUP', error_message=NULL WHERE id=?", (file_id,))


def next_due(conn: sqlite3.Connection, now: float | None = None) -> dict[str, Any] | None:
    row = conn.execute(
        """SELECT q.*, f.relative_path, f.sha256, f.size, f.mime_type, f.local_available, f.cloud_key
           FROM sync_queue q JOIN files f ON f.id=q.file_id
           WHERE q.status IN ('WAITING_BACKUP','ERROR') AND q.next_attempt_at<=?
           ORDER BY q.next_attempt_at, q.id LIMIT 1""",
        (now or time.time(),),
    ).fetchone()
    return dict(row) if row else None


def mark_uploading(conn: sqlite3.Connection, queue_id: int, file_id: int) -> int:
    now = time.time()
    conn.execute("UPDATE sync_queue SET status='UPLOADING', updated_at=? WHERE id=?", (now, queue_id))
    conn.execute("UPDATE files SET sync_status='UPLOADING', error_message=NULL WHERE id=?", (file_id,))
    cur = conn.execute(
        "INSERT INTO sync_history(file_id, relative_path, operation, status, started_at) SELECT id, relative_path, 'UPLOAD', 'UPLOADING', ? FROM files WHERE id=?",
        (now, file_id),
    )
    return int(cur.lastrowid)


def mark_success(conn: sqlite3.Connection, queue_id: int, history_id: int, file_id: int, cloud_key: str) -> None:
    now = time.time()
    conn.execute("DELETE FROM sync_queue WHERE id=?", (queue_id,))
    conn.execute(
        "UPDATE files SET sync_status='SYNCED', cloud_available=1, cloud_key=?, last_backup=?, error_message=NULL WHERE id=?",
        (cloud_key, now, file_id),
    )
    conn.execute("UPDATE sync_history SET status='SYNCED', detail='Integridade remota validada', finished_at=? WHERE id=?", (now, history_id))


def mark_error(conn: sqlite3.Connection, queue_id: int, history_id: int | None, file_id: int, error: str, max_retries: int) -> None:
    row = conn.execute("SELECT attempts FROM sync_queue WHERE id=?", (queue_id,)).fetchone()
    attempts = (int(row["attempts"]) if row else 0) + 1
    delay = min(3600, 15 * (2 ** min(attempts - 1, 8)))
    status = "ERROR"
    conn.execute(
        "UPDATE sync_queue SET status=?, attempts=?, next_attempt_at=?, last_error=?, updated_at=? WHERE id=?",
        (status, attempts, time.time() + delay, error[:1000], time.time(), queue_id),
    )
    conn.execute("UPDATE files SET sync_status='ERROR', error_message=? WHERE id=?", (error[:1000], file_id))
    if history_id:
        conn.execute("UPDATE sync_history SET status='ERROR', detail=?, finished_at=? WHERE id=?", (error[:1000], time.time(), history_id))
    if attempts >= max_retries:
        conn.execute("UPDATE sync_queue SET next_attempt_at=? WHERE id=?", (time.time() + 3600, queue_id))


def list_queue(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT q.*, f.relative_path, f.size FROM sync_queue q
           JOIN files f ON f.id=q.file_id ORDER BY q.updated_at DESC LIMIT ?""", (limit,)
    ).fetchall()
    return [dict(row) for row in rows]


def list_history(conn: sqlite3.Connection, limit: int = 200) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM sync_history ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]
