from __future__ import annotations

import time
from pathlib import Path

from app.database.backup_repository import path_is_protected
from app.database.db import db_session
from app.database.repository import get_file, mark_missing_not_seen, upsert_file
from app.database.sync_repository import enqueue
from app.files.service import FileService


def _changed(previous: dict | None, item: dict) -> bool:
    if previous is None:
        return True
    return (
        int(previous.get("size") or 0) != int(item.get("size") or 0)
        or float(previous.get("modified_at") or 0) != float(item.get("modified_at") or 0)
        or not previous.get("sha256")
    )


def index_one(service: FileService, path: Path, *, calculate_hash: bool = True, queue_backup: bool = True) -> dict:
    now = time.time()
    base = service.info(path)
    base["indexed_at"] = now
    base["last_seen_at"] = now
    with db_session() as conn:
        previous = get_file(conn, base["relative_path"])
        changed = (not base["is_directory"]) and _changed(previous, base)
        if changed and calculate_hash:
            base["sha256"] = service.hash_file(path)
        elif previous:
            base["sha256"] = previous.get("sha256")
        file_id = upsert_file(conn, base)
        if base["is_directory"]:
            conn.execute(
                "INSERT INTO directories(relative_path,discovered_at,updated_at) VALUES(?,?,?) ON CONFLICT(relative_path) DO UPDATE SET updated_at=excluded.updated_at",
                (base["relative_path"], now, now),
            )
        elif changed:
            if previous and previous.get("cloud_available"):
                conn.execute("UPDATE files SET sync_status='LOCAL_ONLY', cloud_available=0 WHERE id=?", (file_id,))
            if queue_backup and path_is_protected(conn, base["relative_path"]):
                enqueue(conn, file_id)
    return base


def index_subtree(service: FileService, path: Path) -> int:
    paths = [path]
    if path.is_dir():
        paths.extend(p for p in path.rglob("*") if not p.is_symlink() and p.name != ".gitkeep")
    count = 0
    for current in paths:
        if current.name == ".gitkeep":
            continue
        try:
            index_one(service, current)
            count += 1
        except FileNotFoundError:
            continue
    return count


def index_tree(service: FileService) -> dict:
    seen: set[str] = set()
    changed = 0
    indexed = 0
    now = time.time()
    with db_session() as conn:
        previous_map = {row["relative_path"]: dict(row) for row in conn.execute("SELECT * FROM files")}
        for path in service.root.rglob("*"):
            try:
                if path.is_symlink() or path.name == ".gitkeep" or path.name.endswith(".drive2-upload"):
                    continue
                item = service.info(path)
                item["indexed_at"] = now
                item["last_seen_at"] = now
                previous = previous_map.get(item["relative_path"])
                item_changed = (not item["is_directory"]) and _changed(previous, item)
                if item_changed:
                    item["sha256"] = service.hash_file(path)
                    changed += 1
                elif previous:
                    item["sha256"] = previous.get("sha256")
                file_id = upsert_file(conn, item)
                if item["is_directory"]:
                    conn.execute(
                        "INSERT INTO directories(relative_path,discovered_at,updated_at) VALUES(?,?,?) ON CONFLICT(relative_path) DO UPDATE SET updated_at=excluded.updated_at",
                        (item["relative_path"], now, now),
                    )
                elif item_changed:
                    if previous and previous.get("cloud_available"):
                        conn.execute("UPDATE files SET cloud_available=0, sync_status='LOCAL_ONLY' WHERE id=?", (file_id,))
                    if path_is_protected(conn, item["relative_path"]):
                        enqueue(conn, file_id)
                seen.add(item["relative_path"])
                indexed += 1
            except FileNotFoundError:
                # A file can disappear between rglob/stat/hash when another device or
                # application changes the shared storage during a scan.
                continue
        missing = mark_missing_not_seen(conn, seen)
    return {"indexed": indexed, "changed": changed, "missing": len(missing)}
