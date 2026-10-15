from pathlib import Path

import pytest

from app.files.service import FileConflictError, FileService, InvalidPathError, TrashService


def test_path_traversal_is_blocked(tmp_path: Path):
    service = FileService(tmp_path / "files")
    with pytest.raises(InvalidPathError):
        service.resolve("../escape.txt")


def test_create_rename_move_delete(tmp_path: Path):
    service = FileService(tmp_path / "files")
    a = service.create_directory("A")
    b = service.create_directory("B")
    f = a / "x.txt"
    f.write_text("ok", encoding="utf-8")
    renamed = service.rename("A/x.txt", "y.txt")
    assert renamed.name == "y.txt"
    moved = service.move("A/y.txt", "B")
    assert moved == b / "y.txt"
    service.delete_permanently("B/y.txt")
    assert not moved.exists()


def test_conflict(tmp_path: Path):
    service = FileService(tmp_path / "files")
    service.create_directory("A")
    with pytest.raises(FileConflictError):
        service.create_directory("A")


def test_sha256(tmp_path: Path):
    service = FileService(tmp_path / "files")
    target = service.root / "hello.txt"
    target.write_text("hello", encoding="utf-8")
    assert service.hash_file(target) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


def test_trash_restore(tmp_path: Path):
    service = FileService(tmp_path / "files")
    trash = TrashService(service, tmp_path / "trash")
    target = service.root / "x.txt"
    target.write_text("data", encoding="utf-8")
    _, trash_name = trash.move_to_trash("x.txt")
    assert not target.exists()
    restored = trash.restore(trash_name, "x.txt")
    assert restored.read_text(encoding="utf-8") == "data"
