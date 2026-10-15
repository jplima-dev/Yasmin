from __future__ import annotations

import json
import sqlite3
from typing import Any


def get_message_by_id(conn: sqlite3.Connection, email_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM email_messages WHERE id=?", (email_id,)).fetchone()
    return dict(row) if row else None


def get_message(conn: sqlite3.Connection, gmail_message_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM email_messages WHERE gmail_message_id=?", (gmail_message_id,)).fetchone()
    return dict(row) if row else None


def insert_message(conn: sqlite3.Connection, item: dict[str, Any]) -> int:
    cur = conn.execute(
        """INSERT INTO email_messages(
            gmail_message_id,thread_id,sender,recipients,subject,message_date,internal_date,
            label_ids,eml_path,eml_sha256,size,backed_up,trashed_in_gmail,archived_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            item["gmail_message_id"], item.get("thread_id"), item.get("sender"), item.get("recipients"),
            item.get("subject"), item.get("message_date"), item.get("internal_date"),
            json.dumps(item.get("label_ids", []), ensure_ascii=False), item["eml_path"], item["eml_sha256"],
            item.get("size", 0), int(item.get("backed_up", False)), int(item.get("trashed_in_gmail", False)),
            item["archived_at"],
        ),
    )
    return int(cur.lastrowid)


def insert_attachment(conn: sqlite3.Connection, email_id: int, item: dict[str, Any]) -> None:
    conn.execute(
        """INSERT INTO email_attachments(email_id,filename,relative_path,mime_type,size,sha256)
           VALUES(?,?,?,?,?,?)""",
        (email_id, item["filename"], item["relative_path"], item.get("mime_type"), item["size"], item["sha256"]),
    )


def mark_backed_up(conn: sqlite3.Connection, email_id: int, backed_up: bool = True) -> None:
    conn.execute("UPDATE email_messages SET backed_up=? WHERE id=?", (int(backed_up), email_id))


def mark_trashed(conn: sqlite3.Connection, email_id: int, trashed: bool = True) -> None:
    conn.execute("UPDATE email_messages SET trashed_in_gmail=? WHERE id=?", (int(trashed), email_id))


def list_messages(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM email_messages ORDER BY internal_date DESC LIMIT ?", (limit,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["label_ids"] = json.loads(item["label_ids"])
        except Exception:
            item["label_ids"] = []
        result.append(item)
    return result


def list_attachments(conn: sqlite3.Connection, email_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM email_attachments WHERE email_id=? ORDER BY id", (email_id,)
    ).fetchall()
    return [dict(row) for row in rows]
