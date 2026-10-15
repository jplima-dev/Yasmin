from __future__ import annotations

import argparse
import shutil
import sqlite3
import time
from pathlib import Path

from app.config import settings


def valid_sqlite(path: Path) -> bool:
    try:
        conn = sqlite3.connect(path)
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        return result == "ok"
    except sqlite3.Error:
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Restaura o banco do Drive2. Pare o servidor antes de usar.")
    parser.add_argument("backup", type=Path)
    args = parser.parse_args()
    backup = args.backup.expanduser().resolve()
    if not backup.is_file() or not valid_sqlite(backup):
        raise SystemExit("Backup inexistente ou SQLite inválido.")
    if settings.database_path.exists():
        safety = settings.database_path.with_name(f"{settings.database_path.name}.before-restore-{int(time.time())}")
        shutil.copy2(settings.database_path, safety)
        print(f"Cópia de segurança atual: {safety}")
    shutil.copy2(backup, settings.database_path)
    if not valid_sqlite(settings.database_path):
        raise SystemExit("A restauração falhou na verificação de integridade.")
    print(f"Restaurado: {settings.database_path}")


if __name__ == "__main__":
    main()
