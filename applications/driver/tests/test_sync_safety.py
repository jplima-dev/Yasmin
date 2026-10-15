from __future__ import annotations

from pathlib import Path

import app.sync.service as sync_module
from app.config import settings
from app.database.backup_repository import set_policy
from app.database.db import db_session, init_db
from app.database.repository import get_file
from app.database.sync_repository import enqueue
from app.files.indexer import index_one
from app.files.service import FileService


def test_mid_upload_mutation_is_not_marked_synced(tmp_path: Path, monkeypatch):
    old_db = settings.database_path
    object.__setattr__(settings, "database_path", tmp_path / "test.db")
    try:
        init_db()
        files = FileService(tmp_path / "files")
        target = files.root / "x.txt"
        target.write_text("AAAA", encoding="utf-8")
        index_one(files, target, calculate_hash=True, queue_backup=False)
        with db_session() as conn:
            set_policy(conn, "", True)
            row = get_file(conn, "x.txt")
            assert row
            enqueue(conn, int(row["id"]))

        class FakeR2:
            def key_for(self, relative_path: str) -> str:
                return f"drive2/files/{relative_path}"

            def upload_verified(self, local_path: Path, key: str, sha256: str, content_type=None):
                # Same-size change is intentionally harder to catch than a size change.
                local_path.write_text("BBBB", encoding="utf-8")
                return {"key": key}

        monkeypatch.setattr(sync_module, "R2Client", FakeR2)
        assert sync_module.SyncService(files).process_one() is True

        with db_session() as conn:
            row = get_file(conn, "x.txt")
            queued = conn.execute("SELECT * FROM sync_queue").fetchone()
            assert row
            assert row["sync_status"] == "ERROR"
            assert row["cloud_available"] == 0
            assert queued and queued["status"] == "ERROR"
    finally:
        object.__setattr__(settings, "database_path", old_db)
