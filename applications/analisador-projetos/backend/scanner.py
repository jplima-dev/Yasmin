"""Filesystem scanning without modifying the analyzed project."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable

from .config import DEFAULT_IGNORED_DIRECTORIES, DEFAULT_IGNORED_FILES
from .languages import identify_language


@dataclass(slots=True)
class ScannedFile:
    absolute_path: Path
    relative_path: Path
    size: int
    extension: str
    language: str | None


@dataclass(slots=True)
class ScanResult:
    root: Path
    files: list[ScannedFile]
    directories: list[Path]
    warnings: list[str]


class ProjectScanner:
    def __init__(
        self,
        ignored_directories: Iterable[str] | None = None,
        ignored_files: Iterable[str] | None = None,
    ) -> None:
        self.ignored_directories = set(ignored_directories or DEFAULT_IGNORED_DIRECTORIES)
        self.ignored_files = set(ignored_files or DEFAULT_IGNORED_FILES)

    def scan(self, root: str | Path) -> ScanResult:
        root_path = Path(root).expanduser().resolve()
        if not root_path.exists():
            raise FileNotFoundError(f"Project path does not exist: {root_path}")
        if not root_path.is_dir():
            raise NotADirectoryError(f"Project path is not a directory: {root_path}")

        files: list[ScannedFile] = []
        directories: list[Path] = []
        warnings: list[str] = []

        def onerror(error: OSError) -> None:
            warnings.append(str(error))

        for current, dirnames, filenames in os.walk(root_path, topdown=True, onerror=onerror, followlinks=False):
            current_path = Path(current)

            # Prune ignored folders and symlinked directories before os.walk descends into them.
            kept_dirs: list[str] = []
            for dirname in dirnames:
                candidate = current_path / dirname
                if dirname in self.ignored_directories:
                    continue
                try:
                    if candidate.is_symlink():
                        continue
                except OSError as exc:
                    warnings.append(f"{candidate}: {exc}")
                    continue
                kept_dirs.append(dirname)
            dirnames[:] = kept_dirs

            if current_path != root_path:
                try:
                    directories.append(current_path.relative_to(root_path))
                except ValueError:
                    pass

            for filename in filenames:
                if filename in self.ignored_files:
                    continue

                absolute = current_path / filename
                try:
                    if absolute.is_symlink() or not absolute.is_file():
                        continue
                    stat = absolute.stat()
                    relative = absolute.relative_to(root_path)
                except (OSError, ValueError) as exc:
                    warnings.append(f"{absolute}: {exc}")
                    continue

                files.append(
                    ScannedFile(
                        absolute_path=absolute,
                        relative_path=relative,
                        size=stat.st_size,
                        extension=absolute.suffix.lower(),
                        language=identify_language(absolute),
                    )
                )

        files.sort(key=lambda item: item.relative_path.as_posix().lower())
        directories.sort(key=lambda path: path.as_posix().lower())
        return ScanResult(root=root_path, files=files, directories=directories, warnings=warnings)
