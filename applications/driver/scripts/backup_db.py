from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from app.config import PROJECT_ROOT, settings


def main() -> None:
    target_dir = PROJECT_ROOT / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"drive2-{time.strftime('%Y%m%d-%H%M%S')}.db"
    source = sqlite3.connect(settings.database_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    print(target)


if __name__ == "__main__":
    main()
