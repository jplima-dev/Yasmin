from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS devices (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, device_type TEXT NOT NULL,
  public_key TEXT NOT NULL UNIQUE, pairing_code TEXT, pairing_status TEXT NOT NULL DEFAULT 'pending',
  pairing_expires_at TEXT, pairing_attempts INTEGER NOT NULL DEFAULT 0, auth_token_hash TEXT,
  online INTEGER NOT NULL DEFAULT 0, network_type TEXT NOT NULL DEFAULT 'unknown',
  battery INTEGER, activity TEXT, last_seen TEXT NOT NULL, permissions TEXT NOT NULL DEFAULT '{}',
  capabilities TEXT NOT NULL DEFAULT '{}',
  revoked INTEGER NOT NULL DEFAULT 0, favorite INTEGER NOT NULL DEFAULT 0, team_id TEXT
);
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_id TEXT, target_id TEXT,
  payload TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL DEFAULT 'created',
  security INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transfers (
  id TEXT PRIMARY KEY, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
  file_name TEXT NOT NULL, total_size INTEGER NOT NULL, received_size INTEGER NOT NULL DEFAULT 0,
  sha256_expected TEXT, sha256_actual TEXT, status TEXT NOT NULL DEFAULT 'offered',
  temp_path TEXT, final_path TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
  content TEXT NOT NULL, behavior TEXT NOT NULL DEFAULT 'save', status TEXT NOT NULL DEFAULT 'sent',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sharebox (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL,
  expires_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS file_requests (
  id TEXT PRIMARY KEY, requester_id TEXT NOT NULL, target_id TEXT NOT NULL,
  note TEXT, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rules (
  id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, name TEXT NOT NULL,
  trigger_json TEXT NOT NULL, action_json TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS teams (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memberships (
  team_id TEXT NOT NULL, device_id TEXT NOT NULL, role TEXT NOT NULL,
  PRIMARY KEY(team_id, device_id)
);
CREATE TABLE IF NOT EXISTS app_metadata (
  key TEXT PRIMARY KEY, value TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transfers_target ON transfers(target_id, status);
CREATE INDEX IF NOT EXISTS idx_messages_target ON messages(target_id, created_at DESC);
"""


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.executescript(SCHEMA)
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(devices)")}
            migrations = {
                "pairing_expires_at": "ALTER TABLE devices ADD COLUMN pairing_expires_at TEXT",
                "pairing_attempts": "ALTER TABLE devices ADD COLUMN pairing_attempts INTEGER NOT NULL DEFAULT 0",
                "auth_token_hash": "ALTER TABLE devices ADD COLUMN auth_token_hash TEXT",
                "capabilities": "ALTER TABLE devices ADD COLUMN capabilities TEXT NOT NULL DEFAULT '{}'",
            }
            for column, statement in migrations.items():
                if column not in columns:
                    connection.execute(statement)

            # Desde a 1.1.1, aparelhos web/Windows aceitam *pedidos* de tela por
            # padrão. Isso não concede captura: navegador/Windows ainda exigem
            # uma ação local para iniciar cada sessão. A marca torna a migração
            # única e preserva qualquer escolha feita depois pelo usuário.
            migration_key = "screen_request_prompt_default_v1"
            migrated = connection.execute(
                "SELECT 1 FROM app_metadata WHERE key=?", (migration_key,)
            ).fetchone()
            if not migrated:
                rows = connection.execute(
                    """SELECT id,permissions FROM devices
                    WHERE pairing_status='paired' AND revoked=0
                      AND device_type IN ('web','windows')"""
                ).fetchall()
                for row in rows:
                    try:
                        permissions = json.loads(row["permissions"] or "{}")
                    except (TypeError, json.JSONDecodeError):
                        permissions = {}
                    permissions["screen_share"] = True
                    connection.execute(
                        "UPDATE devices SET permissions=? WHERE id=?",
                        (json.dumps(permissions), row["id"]),
                    )
                connection.execute(
                    "INSERT INTO app_metadata(key,value) VALUES(?,?)",
                    (migration_key, utcnow()),
                )

    def rows(self, sql: str, parameters: tuple = ()) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return [dict(row) for row in connection.execute(sql, parameters).fetchall()]

    def row(self, sql: str, parameters: tuple = ()) -> dict[str, Any] | None:
        items = self.rows(sql, parameters)
        return items[0] if items else None

    def execute(self, sql: str, parameters: tuple = ()) -> None:
        with self.connection() as connection:
            connection.execute(sql, parameters)

    def register_device(self, data: dict[str, Any], code: str, expires_at: str | None = None) -> dict[str, Any]:
        device_id = data.get("id") or str(uuid.uuid4())
        now = utcnow()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO devices(
                  id,name,device_type,public_key,pairing_code,pairing_status,pairing_expires_at,
                  pairing_attempts,auth_token_hash,last_seen,permissions
                ) VALUES(?,?,?,?,?,'pending',?,0,NULL,?,?)
                ON CONFLICT(public_key) DO UPDATE SET name=excluded.name, device_type=excluded.device_type,
                  pairing_code=excluded.pairing_code, pairing_status='pending',
                  pairing_expires_at=excluded.pairing_expires_at, pairing_attempts=0,
                  auth_token_hash=NULL, last_seen=excluded.last_seen, revoked=0,
                  permissions=excluded.permissions""",
                (device_id, data["name"], data["device_type"], data["public_key"], code, expires_at, now,
                 json.dumps(data.get("permissions", {}))),
            )
        return self.row("SELECT * FROM devices WHERE public_key=?", (data["public_key"],)) or {}

    def confirm_pairing(self, device_id: str, code: str, token_hash: str | None = None) -> bool:
        now = utcnow()
        with self.connection() as connection:
            cursor = connection.execute(
                """UPDATE devices SET pairing_status='paired', pairing_code=NULL,
                  pairing_expires_at=NULL, pairing_attempts=0, auth_token_hash=?, revoked=0
                WHERE id=? AND pairing_code=? AND pairing_status='pending' AND revoked=0
                  AND pairing_attempts < 5
                  AND (pairing_expires_at IS NULL OR pairing_expires_at>?)""",
                (token_hash, device_id, code, now),
            )
            if cursor.rowcount == 1:
                return True
            connection.execute(
                """UPDATE devices SET pairing_attempts=pairing_attempts+1,
                  pairing_code=CASE WHEN pairing_attempts+1>=5 THEN NULL ELSE pairing_code END
                WHERE id=? AND pairing_status='pending' AND revoked=0""",
                (device_id,),
            )
            return False

    def authenticate(self, token_hash: str) -> dict[str, Any] | None:
        return self.row(
            """SELECT * FROM devices
            WHERE auth_token_hash=? AND pairing_status='paired' AND revoked=0""",
            (token_hash,),
        )

    def update_presence(self, device_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        with self.connection() as connection:
            capabilities = data.get("capabilities")
            if capabilities is None:
                connection.execute(
                    """UPDATE devices SET online=1, network_type=?, battery=?, activity=?, last_seen=?
                    WHERE id=? AND pairing_status='paired' AND revoked=0""",
                    (data.get("network_type", "unknown"), data.get("battery"), data.get("activity"), utcnow(), device_id),
                )
            else:
                connection.execute(
                    """UPDATE devices SET online=1, network_type=?, battery=?, activity=?,
                      capabilities=?, last_seen=?
                    WHERE id=? AND pairing_status='paired' AND revoked=0""",
                    (data.get("network_type", "unknown"), data.get("battery"), data.get("activity"),
                     json.dumps(capabilities), utcnow(), device_id),
                )
        return self.row("SELECT * FROM devices WHERE id=?", (device_id,))

    def list_devices(self) -> list[dict[str, Any]]:
        items = self.rows(
            """SELECT id,name,device_type,pairing_status,online,network_type,battery,activity,
              last_seen,permissions,capabilities,revoked,favorite,team_id
            FROM devices
            WHERE revoked=0 AND pairing_status='paired'
            ORDER BY favorite DESC, online DESC, name"""
        )
        for item in items:
            item["permissions"] = json.loads(item.get("permissions") or "{}")
            item["capabilities"] = json.loads(item.get("capabilities") or "{}")
            for field in ("online", "revoked", "favorite"):
                item[field] = bool(item[field])
        return items

    def event(self, kind: str, source_id: str | None, target_id: str | None,
              payload: dict[str, Any], status: str = "created", security: bool = False) -> str:
        event_id = str(uuid.uuid4())
        self.execute(
            "INSERT INTO events VALUES(?,?,?,?,?,?,?,?)",
            (event_id, kind, source_id, target_id, json.dumps(payload), status, int(security), utcnow()),
        )
        return event_id

    def history(self, limit: int = 100, security_only: bool = False) -> list[dict[str, Any]]:
        where = "WHERE events.security=1" if security_only else ""
        items = self.rows(
            f"""SELECT events.*, source.name AS source_name, target.name AS target_name
            FROM events
            LEFT JOIN devices AS source ON source.id=events.source_id
            LEFT JOIN devices AS target ON target.id=events.target_id
            {where}
            ORDER BY events.created_at DESC LIMIT ?""",
            (limit,),
        )
        for item in items:
            item["payload"] = json.loads(item["payload"])
            item["security"] = bool(item["security"])
        historical_names: dict[str, str] = {}
        for row in self.rows("SELECT source_id,payload FROM events WHERE kind='pairing_requested' AND source_id IS NOT NULL"):
            try:
                name = json.loads(row["payload"]).get("name")
            except (TypeError, json.JSONDecodeError):
                name = None
            if name:
                historical_names[row["source_id"]] = name
        transfer_ids = [item["payload"].get("transfer_id") for item in items if item["payload"].get("transfer_id")]
        transfer_names: dict[str, str] = {}
        if transfer_ids:
            placeholders = ",".join("?" for _ in transfer_ids)
            transfer_names = {
                row["id"]: row["file_name"]
                for row in self.rows(f"SELECT id,file_name FROM transfers WHERE id IN ({placeholders})", tuple(transfer_ids))
            }
        for item in items:
            item["source_name"] = item["source_name"] or historical_names.get(item["source_id"])
            item["target_name"] = item["target_name"] or historical_names.get(item["target_id"])
            item["file_name"] = transfer_names.get(item["payload"].get("transfer_id", ""))
        return items

    def create_record(self, table: str, fields: dict[str, Any]) -> dict[str, Any]:
        allowed = {"messages", "sharebox", "file_requests", "rules", "teams", "memberships"}
        if table not in allowed:
            raise ValueError("Tabela não permitida")
        columns = ",".join(fields)
        placeholders = ",".join("?" for _ in fields)
        self.execute(f"INSERT INTO {table}({columns}) VALUES({placeholders})", tuple(fields.values()))
        return fields

    def create_transfer(self, data: dict[str, Any], temp_path: str) -> dict[str, Any]:
        transfer_id = str(uuid.uuid4())
        now = utcnow()
        self.execute(
            """INSERT INTO transfers(id,source_id,target_id,file_name,total_size,sha256_expected,status,temp_path,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (transfer_id, data["source_id"], data["target_id"], data["file_name"], data["total_size"],
             data.get("sha256"), "offered", temp_path, now, now),
        )
        return self.row("SELECT * FROM transfers WHERE id=?", (transfer_id,)) or {}

    def transfer(self, transfer_id: str) -> dict[str, Any] | None:
        return self.row("SELECT * FROM transfers WHERE id=?", (transfer_id,))

    def update_transfer(self, transfer_id: str, **changes: Any) -> dict[str, Any] | None:
        allowed = {"received_size", "sha256_actual", "status", "final_path"}
        clean = {k: v for k, v in changes.items() if k in allowed}
        clean["updated_at"] = utcnow()
        statement = ",".join(f"{key}=?" for key in clean)
        self.execute(f"UPDATE transfers SET {statement} WHERE id=?", tuple(clean.values()) + (transfer_id,))
        return self.transfer(transfer_id)
