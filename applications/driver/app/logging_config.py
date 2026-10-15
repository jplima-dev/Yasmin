from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(level: str, project_root: Path) -> None:
    logs_dir = project_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    logfile = logs_dir / "drive2.log"

    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(getattr(logging, level, logging.INFO))
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
