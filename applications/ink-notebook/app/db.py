"""Acesso ao SQLite (metadados + índice)."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS notebooks(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  notebook_id INTEGER NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
  filename TEXT NOT NULL, ext TEXT NOT NULL DEFAULT '',
  size INTEGER NOT NULL DEFAULT 0, lines INTEGER NOT NULL DEFAULT 0,
  chunk_count INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'indexando', error TEXT,
  added_at TEXT NOT NULL, indexed_at TEXT,
  UNIQUE(notebook_id, filename));
CREATE TABLE IF NOT EXISTS chunks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  notebook_id INTEGER NOT NULL, idx INTEGER NOT NULL,
  start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,
  heading TEXT NOT NULL DEFAULT '', text TEXT NOT NULL, length INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS ix_chunks_nb ON chunks(notebook_id);
CREATE INDEX IF NOT EXISTS ix_chunks_doc ON chunks(document_id);
CREATE TABLE IF NOT EXISTS postings(
  term TEXT NOT NULL,
  chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
  notebook_id INTEGER NOT NULL, tf INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS ix_post_term ON postings(notebook_id, term);
CREATE INDEX IF NOT EXISTS ix_post_chunk ON postings(chunk_id);
CREATE TABLE IF NOT EXISTS activity(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,
  level TEXT NOT NULL DEFAULT 'info', message TEXT NOT NULL, notebook_id INTEGER);
"""

CODE_SCHEMA = """
CREATE TABLE IF NOT EXISTS code_files(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  notebook_id INTEGER NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
  path TEXT NOT NULL, name TEXT NOT NULL, ext TEXT NOT NULL DEFAULT '', lang TEXT NOT NULL DEFAULT 'text',
  size INTEGER NOT NULL DEFAULT 0, lines INTEGER NOT NULL DEFAULT 0, hash TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL DEFAULT '', doc TEXT NOT NULL DEFAULT '', exports TEXT NOT NULL DEFAULT '[]',
  entry INTEGER NOT NULL DEFAULT 0, secret INTEGER NOT NULL DEFAULT 0, secret_lines TEXT NOT NULL DEFAULT '[]',
  status TEXT NOT NULL DEFAULT 'indexado', error TEXT, indexed_at TEXT,
  UNIQUE(notebook_id, path));
CREATE INDEX IF NOT EXISTS ix_cf_nb ON code_files(notebook_id);
CREATE TABLE IF NOT EXISTS code_symbols(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id INTEGER NOT NULL REFERENCES code_files(id) ON DELETE CASCADE, notebook_id INTEGER NOT NULL,
  name TEXT NOT NULL, kind TEXT NOT NULL, parent TEXT NOT NULL DEFAULT '',
  line INTEGER NOT NULL, end_line INTEGER NOT NULL, sig TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS ix_cs_name ON code_symbols(notebook_id, name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_cs_file ON code_symbols(file_id);
CREATE TABLE IF NOT EXISTS code_refs(
  file_id INTEGER NOT NULL REFERENCES code_files(id) ON DELETE CASCADE, notebook_id INTEGER NOT NULL,
  name TEXT NOT NULL, line INTEGER NOT NULL, kind TEXT NOT NULL DEFAULT 'call');
CREATE INDEX IF NOT EXISTS ix_cr_name ON code_refs(notebook_id, name);
CREATE INDEX IF NOT EXISTS ix_cr_file ON code_refs(file_id);
CREATE TABLE IF NOT EXISTS code_edges(
  id INTEGER PRIMARY KEY AUTOINCREMENT, notebook_id INTEGER NOT NULL,
  src_id INTEGER NOT NULL REFERENCES code_files(id) ON DELETE CASCADE,
  dst_id INTEGER REFERENCES code_files(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, target TEXT NOT NULL, line INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS ix_ce_src ON code_edges(src_id);
CREATE INDEX IF NOT EXISTS ix_ce_dst ON code_edges(dst_id);
CREATE INDEX IF NOT EXISTS ix_ce_nb ON code_edges(notebook_id);
CREATE TABLE IF NOT EXISTS code_chunks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id INTEGER NOT NULL REFERENCES code_files(id) ON DELETE CASCADE, notebook_id INTEGER NOT NULL,
  start_line INTEGER NOT NULL, end_line INTEGER NOT NULL, heading TEXT NOT NULL DEFAULT '', text TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_cc_file ON code_chunks(file_id);
CREATE TABLE IF NOT EXISTS code_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS code_history(
  id INTEGER PRIMARY KEY AUTOINCREMENT, notebook_id INTEGER NOT NULL, ts TEXT NOT NULL,
  question TEXT NOT NULL, mode TEXT NOT NULL, answer TEXT NOT NULL);
"""
FTS_SCHEMA = "CREATE VIRTUAL TABLE IF NOT EXISTS code_fts USING fts5(tokens)"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    config.ensure_dirs()
    conn = connect()
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.executescript(CODE_SCHEMA)
    try:
        conn.execute(FTS_SCHEMA)
    except sqlite3.OperationalError:
        pass  # SQLite sem FTS5: a busca de código cai para LIKE
    conn.commit()
    conn.close()


def has_fts(conn) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name='code_fts'").fetchone() is not None
