"""Regras de importação: o que ignorar, linguagens conhecidas e detecção básica de segredos."""
import re
from pathlib import PurePosixPath

MAX_BYTES = 1024 * 1024  # arquivos de código maiores que 1 MB são ignorados

IGNORE_DIRS = {
    ".git", ".svn", ".hg", ".venv", "venv", "env", "node_modules", "__pycache__", ".idea", ".vscode",
    ".next", ".nuxt", ".cache", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", "coverage",
    "dist", "build", "target", "bower_components", "site-packages", ".gradle",
    "screenshots", "screenshot", "prints", "__MACOSX",
}
IGNORE_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".svgz", ".tif", ".tiff", ".psd",
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".mp3", ".wav", ".ogg", ".flac",
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".pyc", ".pyo", ".class", ".jar", ".o", ".a", ".lib",
    ".db", ".sqlite", ".sqlite3", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".pdf",
    ".tmp", ".temp", ".swp", ".bak", ".log", ".lock",
}
IGNORE_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", ".ds_store", "thumbs.db"}

LANG = {
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".py": "python", ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css", ".json": "json", ".php": "php",
    ".md": "markdown", ".markdown": "markdown", ".txt": "text", ".rst": "text",
    ".yml": "text", ".yaml": "text", ".toml": "text", ".ini": "text", ".cfg": "text", ".conf": "text",
    ".sh": "text", ".bat": "text", ".ps1": "text", ".sql": "text", ".xml": "text", ".csv": "text",
    ".java": "text", ".c": "text", ".h": "text", ".cpp": "text", ".cs": "text", ".go": "text",
    ".rs": "text", ".rb": "text", ".vue": "text", ".svelte": "text", ".svg": "text",
}
SPECIAL_NAMES = {"dockerfile", "makefile", "readme", "license", "changelog"}

_SECRET_NAME = re.compile(r"(^|/)(\.env(\.[\w.-]+)?|[^/]*\.(pem|key|p12|pfx|jks|keystore)|id_rsa|id_ed25519|"
                          r"credentials(\.json)?|secrets?\.(json|ya?ml|toml))$", re.I)
_SECRET_SAFE = re.compile(r"\.(example|sample|template|dist)$", re.I)
SECRET_CONTENT = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"(?i)\b(?:password|passwd|senha|secret|api[_-]?key|token)\b\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"),
]


def norm_path(p: str) -> str:
    p = (p or "").replace("\\", "/").lstrip("/")
    parts = [s for s in PurePosixPath(p).parts if s not in ("", ".", "..")]
    return "/".join(parts)


def language_of(path: str):
    if is_secret_file(path):
        return "text", ""  # indexado só por caminho; o conteúdo nunca é guardado
    name = path.rsplit("/", 1)[-1]
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if ext in LANG:
        return LANG[ext], ext
    if name.lower() in SPECIAL_NAMES:
        return "text", ext
    return None, ext


def is_secret_file(path: str) -> bool:
    return bool(_SECRET_NAME.search(path)) and not _SECRET_SAFE.search(path)


def ignore_reason(path: str, size: int = 0):
    """Devolve o motivo de ignorar o arquivo, ou None se ele deve ser indexado."""
    parts = path.split("/")
    for d in parts[:-1]:
        if d in IGNORE_DIRS:
            return f"pasta {d}"
    name = parts[-1]
    low = name.lower()
    if low in IGNORE_NAMES:
        return "arquivo gerado (lock/temporário)"
    if low.endswith((".min.js", ".min.css", ".map")):
        return "arquivo minificado/gerado"
    lang, ext = language_of(path)
    if ext in IGNORE_EXT:
        return f"binário/mídia ({ext})"
    if lang is None:
        return "tipo não indexável" + (f" ({ext})" if ext else "")
    if size > MAX_BYTES:
        return "arquivo grande demais (>1 MB)"
    return None


def find_secret_lines(text: str):
    hits = []
    for i, line in enumerate(text.split("\n"), 1):
        if len(line) < 600 and any(rx.search(line) for rx in SECRET_CONTENT):
            hits.append(i)
    return hits


def redact(text: str) -> str:
    out = text
    for rx in SECRET_CONTENT:
        out = rx.sub("«SEGREDO-OCULTO»", out)
    return out
