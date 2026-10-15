"""Language identification helpers."""

from __future__ import annotations

from pathlib import Path

from .config import LANGUAGE_BY_EXTENSION, LANGUAGE_BY_FILENAME, TEXT_EXTENSIONS


def identify_language(path: Path) -> str | None:
    """Return a display language name for a file, or ``None`` when unknown."""
    filename = path.name.lower()
    if filename in LANGUAGE_BY_FILENAME:
        return LANGUAGE_BY_FILENAME[filename]
    return LANGUAGE_BY_EXTENSION.get(path.suffix.lower())


def is_known_text_extension(path: Path) -> bool:
    """Fast hint for whether a file is expected to be textual."""
    if path.name.lower() in LANGUAGE_BY_FILENAME:
        return True
    return path.suffix.lower() in TEXT_EXTENSIONS
