"""Statistics, content signals and tree construction for a filesystem scan."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .content import inspect_text_file
from .scanner import ScanResult, ScannedFile

_LARGE_FILE_THRESHOLD = 512 * 1024
_MAX_MARKER_ITEMS = 500


def _file_record(file: ScannedFile, lines: int | None) -> dict[str, Any]:
    return {
        "name": file.relative_path.name,
        "path": file.relative_path.as_posix(),
        "extension": file.extension or None,
        "language": file.language,
        "size": file.size,
        "lines": lines,
    }


def build_tree(scan: ScanResult, line_counts: dict[str, int | None]) -> list[dict[str, Any]]:
    """Create a nested, JSON-serializable tree from scan results."""
    root: dict[str, Any] = {"children": {}}

    def ensure_directory(parts: tuple[str, ...]) -> dict[str, Any]:
        node = root
        path_parts: list[str] = []
        for part in parts:
            path_parts.append(part)
            children = node["children"]
            if part not in children:
                children[part] = {
                    "name": part,
                    "type": "directory",
                    "path": "/".join(path_parts),
                    "children": {},
                }
            node = children[part]
        return node

    for directory in scan.directories:
        ensure_directory(directory.parts)

    for file in scan.files:
        parent = ensure_directory(file.relative_path.parent.parts if file.relative_path.parent != Path(".") else ())
        parent["children"][file.relative_path.name] = {
            "name": file.relative_path.name,
            "type": "file",
            "path": file.relative_path.as_posix(),
            "size": file.size,
            "lines": line_counts.get(file.relative_path.as_posix()),
            "language": file.language,
            "extension": file.extension or None,
        }

    def finalize(node: dict[str, Any]) -> list[dict[str, Any]]:
        children = list(node.get("children", {}).values())
        output: list[dict[str, Any]] = []
        for child in sorted(children, key=lambda item: (item["type"] != "directory", item["name"].lower())):
            if child["type"] == "directory":
                child["children"] = finalize(child)
            output.append(child)
        return output

    return finalize(root)


def calculate_statistics(scan: ScanResult) -> dict[str, Any]:
    line_counts: dict[str, int | None] = {}
    text_lines_total = 0

    extension_counts: Counter[str] = Counter()
    language_files: Counter[str] = Counter()
    language_lines: Counter[str] = Counter()
    directory_sizes: defaultdict[str, int] = defaultdict(int)
    direct_files_by_directory: Counter[str] = Counter()
    marker_counts: Counter[str] = Counter({"TODO": 0, "FIXME": 0, "HACK": 0})
    marker_items: list[dict[str, Any]] = []
    marker_files: set[str] = set()

    for file in scan.files:
        rel = file.relative_path.as_posix()
        inspection = inspect_text_file(file.absolute_path, file.language)
        lines = inspection.lines
        line_counts[rel] = lines
        if lines is not None:
            text_lines_total += lines

        if inspection.marker_counts:
            marker_files.add(rel)
            marker_counts.update(inspection.marker_counts)
            if len(marker_items) < _MAX_MARKER_ITEMS:
                available = _MAX_MARKER_ITEMS - len(marker_items)
                for marker in inspection.marker_items[:available]:
                    marker_items.append({"path": rel, **marker})

        extension_counts[file.extension or "[no extension]"] += 1

        if file.language:
            language_files[file.language] += 1
            if lines is not None:
                language_lines[file.language] += lines

        parent_parts = file.relative_path.parent.parts if file.relative_path.parent != Path(".") else ()
        if parent_parts:
            direct_files_by_directory["/".join(parent_parts)] += 1
        for depth in range(1, len(parent_parts) + 1):
            directory_sizes["/".join(parent_parts[:depth])] += file.size

    total_size = sum(file.size for file in scan.files)
    total_files = len(scan.files)
    total_directories = len(scan.directories)

    largest_files = sorted(scan.files, key=lambda item: item.size, reverse=True)[:10]
    largest_file_records = [
        _file_record(file, line_counts.get(file.relative_path.as_posix())) for file in largest_files
    ]

    empty_files = [file for file in scan.files if file.size == 0]
    large_files = [file for file in scan.files if file.size >= _LARGE_FILE_THRESHOLD]
    large_files.sort(key=lambda item: item.size, reverse=True)
    unclassified_files = [file for file in scan.files if file.language is None]

    all_directory_names = {path.as_posix() for path in scan.directories}
    directories_with_child_dir: set[str] = set()
    for directory in scan.directories:
        parent = directory.parent
        if parent != Path("."):
            directories_with_child_dir.add(parent.as_posix())

    empty_directories = sorted(
        name
        for name in all_directory_names
        if direct_files_by_directory[name] == 0 and name not in directories_with_child_dir
    )

    max_depth = max((len(path.parts) for path in scan.directories), default=0)

    largest_directories = [
        {"path": path, "size": size}
        for path, size in sorted(directory_sizes.items(), key=lambda item: item[1], reverse=True)[:10]
    ]

    languages: dict[str, Any] = {}
    known_language_lines = sum(language_lines.values())
    known_language_files = sum(language_files.values())
    all_languages = sorted(set(language_files) | set(language_lines))
    for language in all_languages:
        files = language_files[language]
        lines = language_lines[language]
        languages[language] = {
            "files": files,
            "lines": lines,
            "percent_by_lines": round((lines / known_language_lines * 100), 2) if known_language_lines else 0.0,
            "percent_by_files": round((files / known_language_files * 100), 2) if known_language_files else 0.0,
        }

    extensions = {
        extension: count
        for extension, count in sorted(extension_counts.items(), key=lambda item: (-item[1], item[0]))
    }

    total_markers = sum(marker_counts.values())

    return {
        "summary": {
            "files": total_files,
            "directories": total_directories,
            "lines": text_lines_total,
            "size": total_size,
            "average_file_size": round(total_size / total_files, 2) if total_files else 0,
        },
        "languages": languages,
        "extensions": extensions,
        "largest_files": largest_file_records,
        "structure": {
            "maximum_depth": max_depth,
            "empty_directories": len(empty_directories),
            "empty_directory_paths": empty_directories,
            "largest_directory": largest_directories[0] if largest_directories else None,
            "largest_directories": largest_directories,
        },
        "markers": {
            "counts": {
                "TODO": marker_counts["TODO"],
                "FIXME": marker_counts["FIXME"],
                "HACK": marker_counts["HACK"],
            },
            "total": total_markers,
            "files": len(marker_files),
            "items": marker_items,
            "truncated": total_markers > len(marker_items),
        },
        "insights": {
            "empty_files": {
                "count": len(empty_files),
                "paths": [file.relative_path.as_posix() for file in empty_files[:30]],
            },
            "large_files": {
                "count": len(large_files),
                "threshold": _LARGE_FILE_THRESHOLD,
                "items": [
                    _file_record(file, line_counts.get(file.relative_path.as_posix()))
                    for file in large_files[:10]
                ],
            },
            "unclassified_files": {
                "count": len(unclassified_files),
                "paths": [file.relative_path.as_posix() for file in unclassified_files[:30]],
            },
            "extension_variety": len(extension_counts),
            "warnings": len(scan.warnings),
        },
        "tree": build_tree(scan, line_counts),
    }
