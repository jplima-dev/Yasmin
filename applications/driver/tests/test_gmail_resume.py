from __future__ import annotations

import hashlib
import time
from pathlib import Path

import app.email.gmail as gmail_module
from app.config import settings
from app.database.db import db_session, init_db
from app.database.email_repository import get_message, insert_attachment, insert_message


def test_existing_local_email_can_resume_backup_then_trash(tmp_path: Path, monkeypatch):
    attrs = {
        "database_path": settings.database_path,
        "emails_root": settings.emails_root,
        "attachments_root": settings.attachments_root,
        "gmail_enabled": settings.gmail_enabled,
        "r2_enabled": settings.r2_enabled,
        "gmail_trash_after_backup": settings.gmail_trash_after_backup,
    }
    emails = tmp_path / "emails"
    attachments = tmp_path / "attachments"
    emails.mkdir()
    attachments.mkdir()
    object.__setattr__(settings, "database_path", tmp_path / "test.db")
    object.__setattr__(settings, "emails_root", emails)
    object.__setattr__(settings, "attachments_root", attachments)
    object.__setattr__(settings, "gmail_enabled", True)
    object.__setattr__(settings, "r2_enabled", True)
    object.__setattr__(settings, "gmail_trash_after_backup", True)

    try:
        init_db()
        message_id = "m123"
        raw = b"From: a@example.com\nTo: b@example.com\nSubject: Test\n\nBody\n"
        eml_hash = hashlib.sha256(raw).hexdigest()
        (emails / f"{message_id}.eml").write_bytes(raw)
        attachment_dir = attachments / message_id
        attachment_dir.mkdir()
        attachment_path = attachment_dir / "x.txt"
        attachment_path.write_bytes(b"abc")
        attachment_hash = hashlib.sha256(b"abc").hexdigest()

        with db_session() as conn:
            email_id = insert_message(conn, {
                "gmail_message_id": message_id,
                "thread_id": "t",
                "sender": "a@example.com",
                "recipients": "b@example.com",
                "subject": "Test",
                "message_date": time.time(),
                "internal_date": time.time(),
                "label_ids": [],
                "eml_path": f"{message_id}.eml",
                "eml_sha256": eml_hash,
                "size": len(raw),
                "backed_up": False,
                "trashed_in_gmail": False,
                "archived_at": time.time(),
            })
            insert_attachment(conn, email_id, {
                "filename": "x.txt",
                "relative_path": f"{message_id}/x.txt",
                "mime_type": "text/plain",
                "size": 3,
                "sha256": attachment_hash,
            })

        class FakeR2:
            def key_for(self, path: str, namespace: str = "files") -> str:
                return f"{namespace}/{path}"

            def upload_verified(self, path: Path, key: str, sha256: str, content_type=None):
                assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha256
                return {"key": key}

            def verify_object(self, key: str, sha256: str, size: int):
                return {"key": key}

        trash_calls: list[str] = []

        class Call:
            def execute(self):
                return {}

        class Messages:
            def trash(self, userId: str, id: str):
                trash_calls.append(id)
                return Call()

        class Users:
            def messages(self):
                return Messages()

        class FakeGmail:
            def users(self):
                return Users()

        monkeypatch.setattr(gmail_module, "R2Client", FakeR2)
        service = gmail_module.GmailService()
        monkeypatch.setattr(service, "client", lambda: FakeGmail())
        result = service.archive_message(message_id)

        assert result["status"] == "trashed_after_validation"
        assert trash_calls == [message_id]
        with db_session() as conn:
            row = get_message(conn, message_id)
            assert row and row["backed_up"] == 1 and row["trashed_in_gmail"] == 1
    finally:
        for name, value in attrs.items():
            object.__setattr__(settings, name, value)
