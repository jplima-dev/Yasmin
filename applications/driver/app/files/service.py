from __future__ import annotations

import hashlib
import mimetypes
import os
import shutil
import time
from pathlib import Path


class InvalidPathError(ValueError):
    pass


class FileConflictError(FileExistsError):
    pass


class FileService:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative_path: str = "") -> Path:
        relative_path = (relative_path or "").replace("\\", "/").strip("/")
        candidate = (self.root / relative_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise InvalidPathError("Caminho fora da área de armazenamento do Drive2.") from exc
        return candidate

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def info(self, path: Path, *, sha256: str | None = None) -> dict:
        if path.is_symlink():
            raise InvalidPathError("Links simbólicos não são indexados pelo Drive2.")
        stat = path.stat()
        rel = self.relative(path)
        parent = Path(rel).parent.as_posix() if rel else ""
        if parent == ".":
            parent = ""
        return {
            "name": path.name if rel else "InkDriver",
            "relative_path": rel,
            "parent_path": parent,
            "is_directory": path.is_dir(),
            "size": 0 if path.is_dir() else stat.st_size,
            "mime_type": None if path.is_dir() else (mimetypes.guess_type(path.name)[0] or "application/octet-stream"),
            "sha256": sha256,
            "created_at": stat.st_ctime,
            "modified_at": stat.st_mtime,
        }

    def list_dir(self, relative_path: str = "") -> list[dict]:
        target = self.resolve(relative_path)
        if not target.exists():
            raise FileNotFoundError(relative_path)
        if not target.is_dir():
            raise NotADirectoryError(relative_path)
        items = []
        for child in target.iterdir():
            if child.is_symlink() or child.name == ".gitkeep" or child.name.endswith(".drive2-upload"):
                continue
            items.append(self.info(child))
        items.sort(key=lambda item: (not item["is_directory"], item["name"].lower()))
        return items

    def create_directory(self, relative_path: str) -> Path:
        target = self.resolve(relative_path)
        if target.exists():
            raise FileConflictError(relative_path)
        target.mkdir(parents=True, exist_ok=False)
        return target

    def rename(self, relative_path: str, new_name: str) -> Path:
        if not new_name or new_name in {".", ".."} or "/" in new_name or "\\" in new_name:
            raise InvalidPathError("Nome inválido.")
        source = self.resolve(relative_path)
        if not source.exists():
            raise FileNotFoundError(relative_path)
        destination = self.resolve(self.relative(source.with_name(new_name)))
        if destination.exists():
            raise FileConflictError(destination.name)
        source.rename(destination)
        return destination

    def move(self, source_path: str, destination_dir: str) -> Path:
        source = self.resolve(source_path)
        destination_folder = self.resolve(destination_dir)
        if not source.exists():
            raise FileNotFoundError(source_path)
        if not destination_folder.is_dir():
            raise NotADirectoryError(destination_dir)
        destination = self.resolve(self.relative(destination_folder / source.name))
        if destination.exists():
            raise FileConflictError(destination.name)
        if source.is_dir():
            try:
                destination_folder.relative_to(source)
            except ValueError:
                pass
            else:
                raise InvalidPathError("Não é possível mover uma pasta para dentro dela mesma.")
        return Path(shutil.move(str(source), str(destination)))

    def delete_permanently(self, relative_path: str) -> None:
        target = self.resolve(relative_path)
        if target == self.root:
            raise InvalidPathError("A raiz do Drive2 não pode ser excluída.")
        if not target.exists():
            raise FileNotFoundError(relative_path)
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    def storage_usage(self) -> dict:
        usage = shutil.disk_usage(self.root)
        return {"total": usage.total, "used": usage.used, "free": usage.free}

    def ensure_space_for(self, expected_bytes: int) -> None:
        if expected_bytes > 0 and self.storage_usage()["free"] < expected_bytes:
            raise OSError("Espaço insuficiente no armazenamento.")

    def hash_file(self, path: Path, chunk_size: int = 1024 * 1024) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_size), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def atomic_destination(destination: Path) -> Path:
        return destination.with_name(f".{destination.name}.drive2-upload")

    def commit_upload(self, temp_path: Path, destination: Path) -> Path:
        if destination.exists():
            raise FileConflictError(destination.name)
        os.replace(temp_path, destination)
        return destination

    def touch_inbox(self) -> Path:
        inbox = self.resolve("Inbox")
        inbox.mkdir(exist_ok=True)
        return inbox

    @staticmethod
    def unique_name(folder: Path, name: str) -> Path:
        candidate = folder / name
        if not candidate.exists():
            return candidate
        stem, suffix = Path(name).stem, Path(name).suffix
        i = 2
        while True:
            candidate = folder / f"{stem} ({i}){suffix}"
            if not candidate.exists():
                return candidate
            i += 1


class TrashService:
    def __init__(self, files: FileService, trash_root: Path):
        self.files = files
        self.trash_root = trash_root.resolve()
        self.trash_root.mkdir(parents=True, exist_ok=True)

    def move_to_trash(self, relative_path: str) -> tuple[Path, str]:
        source = self.files.resolve(relative_path)
        if source == self.files.root:
            raise InvalidPathError("A raiz do Drive2 não pode ser movida para a lixeira.")
        if not source.exists():
            raise FileNotFoundError(relative_path)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        safe_rel = relative_path.replace("/", "__") or source.name
        destination = self.files.unique_name(self.trash_root, f"{stamp}__{safe_rel}")
        shutil.move(str(source), str(destination))
        return destination, destination.name

    def restore(self, trash_name: str, original_path: str) -> Path:
        source = (self.trash_root / Path(trash_name).name).resolve()
        try:
            source.relative_to(self.trash_root)
        except ValueError as exc:
            raise InvalidPathError("Entrada de lixeira inválida.") from exc
        if not source.exists():
            raise FileNotFoundError(trash_name)
        destination = self.files.resolve(original_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise FileConflictError(original_path)
        shutil.move(str(source), str(destination))
        return destination

    def purge(self, trash_name: str) -> None:
        target = (self.trash_root / Path(trash_name).name).resolve()
        try:
            target.relative_to(self.trash_root)
        except ValueError as exc:
            raise InvalidPathError("Entrada de lixeira inválida.") from exc
        if not target.exists():
            raise FileNotFoundError(trash_name)
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
