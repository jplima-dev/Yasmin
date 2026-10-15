"""Read-only content inspection helpers used by project statistics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
import tokenize

from .languages import is_known_text_extension

_SAMPLE_SIZE = 8192
_MARKER_PATTERN_BYTES = re.compile(rb"\b(TODO|FIXME|HACK)\b", re.IGNORECASE)
_MARKER_PATTERN_TEXT = re.compile(r"\b(TODO|FIXME|HACK)\b", re.IGNORECASE)
_MAX_STORED_MARKERS_PER_FILE = 50

_HASH_COMMENT_LANGUAGES = {
    "Shell", "PowerShell", "Ruby", "R", "YAML", "TOML", "Config",
    "Makefile", "Dockerfile", "CMake",
}
_SLASH_COMMENT_LANGUAGES = {
    "JavaScript", "TypeScript", "Java", "Kotlin", "C", "C/C++ Header",
    "C++", "C++ Header", "C#", "Go", "Rust", "Swift", "Dart", "PHP",
    "SCSS", "Less", "Vue", "Svelte", "Astro",
}
_BLOCK_COMMENT_LANGUAGES = {"CSS", "Sass"}
_DASH_COMMENT_LANGUAGES = {"SQL", "Lua"}
_HTML_COMMENT_LANGUAGES = {"HTML", "XML"}
_SEMICOLON_COMMENT_LANGUAGES = {"INI"}
_BATCH_COMMENT_LANGUAGES = {"Batch"}


@dataclass(slots=True)
class TextInspection:
    lines: int | None
    marker_counts: Counter[str]
    marker_items: list[dict[str, object]]


def looks_binary(path: Path) -> bool:
    """Conservatively detect binary files using a small byte sample."""
    try:
        with path.open("rb") as handle:
            sample = handle.read(_SAMPLE_SIZE)
    except OSError:
        return True

    if not sample:
        return False
    if b"\x00" in sample:
        return True

    if is_known_text_extension(path):
        return False

    suspicious = sum(byte < 9 or 13 < byte < 32 for byte in sample)
    return suspicious / len(sample) > 0.08


def _is_comment_marker(raw_line: bytes, marker_start: int, language: str | None) -> bool:
    """Use lightweight language-aware rules to avoid matching ordinary strings/text."""
    if not language or language in {"Markdown", "MDX", "JSON", "GraphQL"}:
        return False

    prefix = raw_line[:marker_start]
    stripped = prefix.lstrip()

    if language in _HASH_COMMENT_LANGUAGES:
        return b"#" in prefix
    if language in _SLASH_COMMENT_LANGUAGES:
        return b"//" in prefix or b"/*" in prefix or stripped.startswith(b"*")
    if language in _BLOCK_COMMENT_LANGUAGES:
        return b"/*" in prefix or stripped.startswith(b"*")
    if language in _DASH_COMMENT_LANGUAGES:
        return b"--" in prefix or b"/*" in prefix or stripped.startswith(b"*")
    if language in _HTML_COMMENT_LANGUAGES:
        return b"<!--" in prefix
    if language in _SEMICOLON_COMMENT_LANGUAGES:
        return stripped.startswith((b";", b"#"))
    if language in _BATCH_COMMENT_LANGUAGES:
        upper = stripped.upper()
        return upper.startswith(b"REM ") or upper.startswith(b"::")
    return False


def _inspect_python_markers(path: Path) -> tuple[Counter[str], list[dict[str, object]]]:
    counts: Counter[str] = Counter()
    items: list[dict[str, object]] = []
    try:
        with path.open("rb") as handle:
            tokens = tokenize.tokenize(handle.readline)
            for token in tokens:
                if token.type != tokenize.COMMENT:
                    continue
                matches = list(_MARKER_PATTERN_TEXT.finditer(token.string))
                if not matches:
                    continue
                snippet = token.line.strip()
                if len(snippet) > 180:
                    snippet = f"{snippet[:177]}..."
                for match in matches:
                    marker = match.group(1).upper()
                    counts[marker] += 1
                    if len(items) < _MAX_STORED_MARKERS_PER_FILE:
                        items.append({"type": marker, "line": token.start[0], "snippet": snippet})
    except (OSError, SyntaxError, UnicodeDecodeError, tokenize.TokenError):
        return Counter(), []
    return counts, items


def inspect_text_file(path: Path, language: str | None = None) -> TextInspection:
    """Count physical lines and find TODO/FIXME/HACK markers in source comments.

    Marker totals remain exact even when the number of stored marker snippets is
    capped for a single file.
    """
    if looks_binary(path):
        return TextInspection(lines=None, marker_counts=Counter(), marker_items=[])

    marker_counts: Counter[str] = Counter()
    marker_items: list[dict[str, object]] = []
    line_count = 0

    try:
        with path.open("rb") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line_count = line_number
                if language == "Python":
                    continue

                matches = list(_MARKER_PATTERN_BYTES.finditer(raw_line))
                if not matches:
                    continue

                snippet = raw_line.decode("utf-8", errors="replace").strip()
                if len(snippet) > 180:
                    snippet = f"{snippet[:177]}..."

                for match in matches:
                    if not _is_comment_marker(raw_line, match.start(), language):
                        continue
                    marker = match.group(1).decode("ascii").upper()
                    marker_counts[marker] += 1
                    if len(marker_items) < _MAX_STORED_MARKERS_PER_FILE:
                        marker_items.append({"type": marker, "line": line_number, "snippet": snippet})
    except OSError:
        return TextInspection(lines=None, marker_counts=Counter(), marker_items=[])

    if language == "Python":
        marker_counts, marker_items = _inspect_python_markers(path)

    return TextInspection(lines=line_count, marker_counts=marker_counts, marker_items=marker_items)
