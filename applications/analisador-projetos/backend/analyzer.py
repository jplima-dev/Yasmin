"""High-level orchestration for project analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Any

from .config import DEFAULT_IGNORED_DIRECTORIES, DEFAULT_IGNORED_FILES
from .scanner import ProjectScanner
from .statistics import calculate_statistics


class ProjectAnalyzer:
    """Analyze a project directory without modifying its contents."""

    def __init__(
        self,
        ignored_directories: Iterable[str] | None = None,
        ignored_files: Iterable[str] | None = None,
    ) -> None:
        self.ignored_directories = set(ignored_directories or DEFAULT_IGNORED_DIRECTORIES)
        self.ignored_files = set(ignored_files or DEFAULT_IGNORED_FILES)
        self.scanner = ProjectScanner(self.ignored_directories, self.ignored_files)

    def analyze(self, path: str | Path) -> dict[str, Any]:
        scan = self.scanner.scan(path)
        statistics = calculate_statistics(scan)
        return {
            "project": {
                "name": scan.root.name or str(scan.root),
                "path": str(scan.root),
            },
            **statistics,
            "ignored": {
                "directories": sorted(self.ignored_directories),
                "files": sorted(self.ignored_files),
            },
            "warnings": scan.warnings,
        }
