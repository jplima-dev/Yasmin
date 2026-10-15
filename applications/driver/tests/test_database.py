from pathlib import Path

from app.database.backup_repository import path_is_protected, set_policy
from app.database.db import connect, init_db
from app.database.repository import get_file, remap_path_prefix, upsert_file
from app.database.sync_repository import enqueue, next_due


def test_schema_and_queue(tmp_path: Path):
    db = tmp_path / "test.db"
    init_db(db)
    conn = connect(db)
    try:
        set_policy(conn, "Documentos", True)
        assert path_is_protected(conn, "Documentos/a.txt")
        assert not path_is_protected(conn, "Downloads/a.txt")
        file_id = upsert_file(conn, {
            "name": "a.txt", "relative_path": "Documentos/a.txt", "parent_path": "Documentos",
            "is_directory": False, "size": 3, "mime_type": "text/plain", "sha256": "abc",
            "created_at": 1.0, "modified_at": 1.0, "indexed_at": 1.0, "last_seen_at": 1.0,
        })
        enqueue(conn, file_id)
        conn.commit()
        due = next_due(conn, now=9999999999)
        assert due and due["relative_path"] == "Documentos/a.txt"
    finally:
        conn.close()


def test_remap_preserves_row(tmp_path: Path):
    db = tmp_path / "test.db"
    init_db(db)
    conn = connect(db)
    try:
        upsert_file(conn, {
            "name": "a.txt", "relative_path": "A/a.txt", "parent_path": "A", "is_directory": False,
            "size": 1, "mime_type": "text/plain", "sha256": "abc", "created_at": 1.0,
            "modified_at": 1.0, "indexed_at": 1.0, "last_seen_at": 1.0,
        })
        conn.execute("UPDATE files SET favorite=1, cloud_available=1, sync_status='SYNCED' WHERE relative_path='A/a.txt'")
        remap_path_prefix(conn, "A", "B")
        conn.commit()
        item = get_file(conn, "B/a.txt")
        assert item and item["favorite"] == 1 and item["cloud_available"] == 1
    finally:
        conn.close()
