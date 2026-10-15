"""Configuração e caminhos.

data/
  notebooks/<slug>/sources/   <- arquivos ORIGINAIS (o que você adicionou)
  index/ink.db                <- dados INTERNOS (metadados, trechos, índice, atividade)
"""
import os
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("INK_DATA_DIR", ROOT / "data")).resolve()
NOTEBOOKS_DIR = DATA_DIR / "notebooks"
INDEX_DIR = DATA_DIR / "index"
DB_PATH = INDEX_DIR / "ink.db"
FRONTEND_DIR = ROOT / "frontend"

HOST = os.environ.get("INK_HOST", "127.0.0.1")
PORT = int(os.environ.get("INK_PORT", "8001"))
MAX_FILE_MB = 25
MAX_PREVIEW_LINES = 20000


def workspace_core_origin() -> str:
    """Return only a loopback Core origin supplied by Workspace OS."""
    value = os.environ.get("WORKSPACE_CORE_ORIGIN", "").strip().rstrip("/")
    try:
        parsed = urlparse(value)
    except ValueError:
        return ""
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return ""
    return value


def ensure_dirs():
    NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)


def sources_dir(slug: str) -> Path:
    return NOTEBOOKS_DIR / slug / "sources"


def source_path(slug: str, filename: str) -> Path:
    return sources_dir(slug) / filename
