from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.database import Database


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.directory.name) / "bridge.sqlite3")
        self.db.initialize()

    def tearDown(self) -> None:
        self.directory.cleanup()

    def paired_device(self, name: str = "Notebook") -> dict:
        device = self.db.register_device({
            "name": name, "device_type": "windows", "public_key": f"key-{name}-12345678",
            "permissions": {"remote_ring": True},
        }, "123456")
        self.assertTrue(self.db.confirm_pairing(device["id"], "123456"))
        return device

    def test_pairing_presence_and_revocation_fields(self) -> None:
        device = self.paired_device()
        updated = self.db.update_presence(device["id"], {
            "network_type": "lan", "battery": 75, "activity": "VS Code",
            "capabilities": {"screen_capture": True, "webrtc": True},
        })
        self.assertEqual(updated["battery"], 75)
        listed = self.db.list_devices()[0]
        self.assertTrue(listed["capabilities"]["screen_capture"])
        self.assertEqual(updated["activity"], "VS Code")
        listed = self.db.list_devices()[0]
        self.assertTrue(listed["online"])
        self.assertTrue(listed["permissions"]["remote_ring"])

    def test_history_keeps_security_filter(self) -> None:
        source, target = self.paired_device("History Source"), self.paired_device("History Target")
        self.db.event("ordinary", source["id"], target["id"], {"value": 1})
        self.db.event("pairing_failed", None, None, {"value": 2}, security=True)
        history = self.db.history()
        self.assertEqual(len(history), 2)
        ordinary = next(item for item in history if item["kind"] == "ordinary")
        self.assertEqual(ordinary["source_name"], "History Source")
        self.assertEqual(ordinary["target_name"], "History Target")
        security = self.db.history(security_only=True)
        self.assertEqual([item["kind"] for item in security], ["pairing_failed"])

    def test_history_keeps_name_after_device_is_removed(self) -> None:
        device = self.paired_device("Old Notebook")
        self.db.event("pairing_requested", device["id"], None, {"name": "Old Notebook"}, security=True)
        self.db.event("ordinary", device["id"], None, {})
        self.db.execute("DELETE FROM devices WHERE id=?", (device["id"],))

        ordinary = next(item for item in self.db.history() if item["kind"] == "ordinary")
        self.assertEqual(ordinary["source_name"], "Old Notebook")

    def test_transfer_state_is_persisted(self) -> None:
        source, target = self.paired_device("Source"), self.paired_device("Target")
        temporary = Path(self.directory.name) / "part"
        temporary.write_bytes(b"bridge")
        expected = hashlib.sha256(b"bridge").hexdigest()
        transfer = self.db.create_transfer({
            "source_id": source["id"], "target_id": target["id"], "file_name": "a.txt",
            "total_size": 6, "sha256": expected,
        }, str(temporary))
        updated = self.db.update_transfer(transfer["id"], received_size=6, sha256_actual=expected, status="completed")
        self.assertEqual(updated["status"], "completed")
        self.assertEqual(updated["sha256_actual"], expected)

    def test_initialize_migrates_devices_created_before_token_auth(self) -> None:
        legacy_path = Path(self.directory.name) / "legacy.sqlite3"
        connection = sqlite3.connect(legacy_path)
        try:
            connection.execute("""CREATE TABLE devices (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, device_type TEXT NOT NULL,
              public_key TEXT NOT NULL UNIQUE, pairing_code TEXT,
              pairing_status TEXT NOT NULL DEFAULT 'pending', online INTEGER NOT NULL DEFAULT 0,
              network_type TEXT NOT NULL DEFAULT 'unknown', battery INTEGER, activity TEXT,
              last_seen TEXT NOT NULL, permissions TEXT NOT NULL DEFAULT '{}',
              revoked INTEGER NOT NULL DEFAULT 0, favorite INTEGER NOT NULL DEFAULT 0, team_id TEXT
            )""")
            connection.commit()
        finally:
            connection.close()
        legacy = Database(legacy_path)
        legacy.initialize()
        connection = sqlite3.connect(legacy_path)
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(devices)")}
            connection.execute("PRAGMA journal_mode=DELETE")
        finally:
            connection.close()
        self.assertTrue({"pairing_expires_at", "pairing_attempts", "auth_token_hash"} <= columns)


if __name__ == "__main__":
    unittest.main()
