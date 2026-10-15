from __future__ import annotations

import sqlite3
import time
from typing import Any

SYNC_STATUSES = {"LOCAL_ONLY", "WAITING_BACKUP", "UPLOADING", "SYNCED", "ERROR", "CLOUD_ONLY"}


def get_file(conn: sqlite3.Connection, relative_path: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM files WHERE relative_path=?", (relative_path,)).fetchone()
    return dict(row) if row else None


def get_file_by_id(conn: sqlite3.Connection, file_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM files WHERE id=?", (file_id,)).fetchone()
    return dict(row) if row else None


def upsert_file(conn: sqlite3.Connection, item: dict[str, Any]) -> int:
    now = item.get("indexed_at", time.time())
    conn.execute(
        """
        INSERT INTO files (
            name, relative_path, parent_path, is_directory, size, mime_type, sha256,
            created_at, modified_at, indexed_at, last_seen_at, local_available,
            cloud_available, sync_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 'LOCAL_ONLY')
        ON CONFLICT(relative_path) DO UPDATE SET
            name=excluded.name,
            parent_path=excluded.parent_path,
            is_directory=excluded.is_directory,
            size=excluded.size,
            mime_type=excluded.mime_type,
            sha256=COALESCE(excluded.sha256, files.sha256),
            created_at=excluded.created_at,
            modified_at=excluded.modified_at,
            indexed_at=excluded.indexed_at,
            last_seen_at=excluded.last_seen_at,
            local_available=1,
            error_message=NULL
        """,
        (
            item["name"], item["relative_path"], item["parent_path"], int(item["is_directory"]),
            item["size"], item.get("mime_type"), item.get("sha256"), item.get("created_at"),
            item.get("modified_at"), now, item.get("last_seen_at", now),
        ),
    )
    row = conn.execute("SELECT id FROM files WHERE relative_path=?", (item["relative_path"],)).fetchone()
    return int(row["id"])


def update_hash(conn: sqlite3.Connection, relative_path: str, sha256: str, indexed_at: float | None = None) -> None:
    conn.execute(
        "UPDATE files SET sha256=?, indexed_at=?, last_seen_at=?, local_available=1 WHERE relative_path=?",
        (sha256, indexed_at or time.time(), time.time(), relative_path),
    )


def delete_path(conn: sqlite3.Connection, relative_path: str) -> None:
    prefix = f"{relative_path}/%" if relative_path else "%"
    conn.execute("DELETE FROM files WHERE relative_path = ? OR relative_path LIKE ?", (relative_path, prefix))


def mark_missing_not_seen(conn: sqlite3.Connection, seen: set[str]) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM files WHERE local_available=1").fetchall()
    missing = [dict(row) for row in rows if row["relative_path"] not in seen]
    for row in missing:
        status = "CLOUD_ONLY" if row["cloud_available"] else "ERROR"
        error = None if row["cloud_available"] else "Arquivo local não encontrado durante a varredura."
        conn.execute(
            "UPDATE files SET local_available=0, sync_status=?, error_message=? WHERE id=?",
            (status, error, row["id"]),
        )
    return missing


def search(conn: sqlite3.Connection, query: str, limit: int = 100) -> list[dict[str, Any]]:
    like = f"%{query}%"
    rows = conn.execute(
        """SELECT * FROM files
           WHERE (name LIKE ? COLLATE NOCASE OR relative_path LIKE ? COLLATE NOCASE)
           ORDER BY local_available DESC, is_directory DESC, name COLLATE NOCASE
           LIMIT ?""",
        (like, like, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def list_recent(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM files WHERE is_directory=0 ORDER BY modified_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(row) for row in rows]


def list_favorites(conn: sqlite3.Connection, limit: int = 500) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM files WHERE favorite=1 ORDER BY is_directory DESC, name COLLATE NOCASE LIMIT ?", (limit,)
    ).fetchall()
    return [dict(row) for row in rows]


def set_favorite(conn: sqlite3.Connection, relative_path: str, favorite: bool) -> dict[str, Any] | None:
    conn.execute("UPDATE files SET favorite=? WHERE relative_path=?", (int(favorite), relative_path))
    return get_file(conn, relative_path)


def set_sync_state(
    conn: sqlite3.Connection,
    file_id: int,
    status: str,
    *,
    cloud_available: bool | None = None,
    cloud_key: str | None = None,
    last_backup: float | None = None,
    error_message: str | None = None,
) -> None:
    if status not in SYNC_STATUSES:
        raise ValueError(f"Status inválido: {status}")
    fields = ["sync_status=?", "error_message=?"]
    values: list[Any] = [status, error_message]
    if cloud_available is not None:
        fields.append("cloud_available=?")
        values.append(int(cloud_available))
    if cloud_key is not None:
        fields.append("cloud_key=?")
        values.append(cloud_key)
    if last_backup is not None:
        fields.append("last_backup=?")
        values.append(last_backup)
    values.append(file_id)
    conn.execute(f"UPDATE files SET {', '.join(fields)} WHERE id=?", values)


def stats(conn: sqlite3.Connection) -> dict[str, Any]:
    file_count = conn.execute("SELECT COUNT(*) c FROM files WHERE is_directory=0 AND local_available=1").fetchone()["c"]
    protected = conn.execute("SELECT COUNT(*) c FROM files WHERE is_directory=0 AND cloud_available=1").fetchone()["c"]
    waiting = conn.execute("SELECT COUNT(*) c FROM files WHERE sync_status='WAITING_BACKUP'").fetchone()["c"]
    errors = conn.execute("SELECT COUNT(*) c FROM files WHERE sync_status='ERROR'").fetchone()["c"]
    last = conn.execute("SELECT MAX(last_backup) v FROM files").fetchone()["v"]
    return {"files": file_count, "protected": protected, "waiting": waiting, "errors": errors, "last_backup": last}


def remap_path_prefix(conn: sqlite3.Connection, old_prefix: str, new_prefix: str) -> None:
    old_prefix = old_prefix.strip("/")
    new_prefix = new_prefix.strip("/")
    rows = conn.execute(
        "SELECT id, relative_path FROM files WHERE relative_path=? OR relative_path LIKE ? ORDER BY LENGTH(relative_path)",
        (old_prefix, f"{old_prefix}/%"),
    ).fetchall()
    mapping: list[tuple[int, str]] = []
    for row in rows:
        old_path = row["relative_path"]
        suffix = old_path[len(old_prefix):].lstrip("/") if old_prefix else old_path
        new_path = new_prefix if not suffix else f"{new_prefix}/{suffix}" if new_prefix else suffix
        mapping.append((row["id"], new_path))
    # Temporary names make the operation safe even if paths overlap logically.
    token = f".__drive2_remap_{int(time.time() * 1000000)}__"
    for file_id, _ in mapping:
        conn.execute("UPDATE files SET relative_path=? || id WHERE id=?", (token, file_id))
    for file_id, new_path in mapping:
        name = new_path.rsplit("/", 1)[-1] if new_path else "Drive2"
        parent = new_path.rsplit("/", 1)[0] if "/" in new_path else ""
        conn.execute(
            "UPDATE files SET relative_path=?, name=?, parent_path=? WHERE id=?",
            (new_path, name, parent, file_id),
        )


def mark_path_unavailable(conn: sqlite3.Connection, relative_path: str) -> None:
    prefix = relative_path.strip("/")
    rows = conn.execute(
        "SELECT id,cloud_available FROM files WHERE relative_path=? OR relative_path LIKE ?",
        (prefix, f"{prefix}/%"),
    ).fetchall()
    for row in rows:
        status = "CLOUD_ONLY" if row["cloud_available"] else "LOCAL_ONLY"
        conn.execute("DELETE FROM sync_queue WHERE file_id=?", (row["id"],))
        conn.execute(
            "UPDATE files SET local_available=0, sync_status=?, error_message=NULL WHERE id=?",
            (status, row["id"]),
        )
