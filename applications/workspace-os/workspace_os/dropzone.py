from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO
from uuid import uuid4


UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024
MAX_CHUNK_SIZE = 64 * 1024 * 1024
DISK_RESERVE = 64 * 1024 * 1024


class DropzoneStore:
    def __init__(self, data_dir: Path, *, max_items: int = 30) -> None:
        self.root = (data_dir / "dropzone").resolve()
        self.index_path = self.root / "history.json"
        self.upload_root = self.root / ".uploads"
        self.folder_root = self.root / "folders"
        self.max_items = max_items
        self._lock = threading.RLock()

    def _load(self) -> list[dict[str, Any]]:
        if not self.index_path.exists():
            return []
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return payload if isinstance(payload, list) else []

    def _write(self, items: list[dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.index_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.index_path)

    def _add_record(self, record: dict[str, Any]) -> dict[str, Any]:
        items = [record, *[item for item in self._load() if item.get("id") != record["id"]]]
        removed = items[self.max_items :]
        for old in removed:
            self._purge_payload(old)
        self._write(items[: self.max_items])
        return record

    def _purge_payload(self, record: dict[str, Any]) -> None:
        item_id = str(record.get("id", ""))
        if not self._valid_id(item_id):
            return
        (self.root / f"{item_id}.bin").unlink(missing_ok=True)
        shutil.rmtree(self.folder_root / item_id, ignore_errors=True)

    def add(self, *, name: str, mime: str, content: bytes, kind: str = "file", last_modified: int = 0) -> dict[str, Any]:
        if kind == "folder":
            return self.begin_folder(name=name, expected_files=0, expected_size=0)
        upload = self.begin_upload(name=name, mime=mime, expected_size=len(content), last_modified=last_modified)
        if content:
            from io import BytesIO
            self.append_upload(upload["uploadId"], 0, BytesIO(content), len(content))
        return self.finish_upload(upload["uploadId"])

    def begin_upload(
        self, *, name: str, mime: str, expected_size: int, last_modified: int = 0,
        folder_id: str = "", relative_path: str = "",
    ) -> dict[str, Any]:
        size = int(expected_size)
        if size < 0:
            raise ValueError("Tamanho de arquivo inválido.")
        with self._lock:
            self.upload_root.mkdir(parents=True, exist_ok=True)
            free = shutil.disk_usage(self.root).free
            if size > max(0, free - DISK_RESERVE):
                raise ValueError("Não há espaço livre suficiente para receber este arquivo.")
            if folder_id:
                record = self._find_record(folder_id)
                if record.get("kind") != "folder":
                    raise ValueError("Pasta de destino inválida.")
            upload_id = uuid4().hex
            metadata = {
                "uploadId": upload_id,
                "name": Path(name or "arquivo").name[:240],
                "type": str(mime or "application/octet-stream")[:160],
                "expectedSize": size,
                "lastModified": max(0, int(last_modified or 0)),
                "folderId": folder_id,
                "relativePath": self._safe_relative_path(relative_path or name),
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            self._upload_metadata_path(upload_id).write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            self._upload_part_path(upload_id).touch()
            return {"uploadId": upload_id, "offset": 0, "chunkSize": UPLOAD_CHUNK_SIZE, "size": size}

    def append_upload(self, upload_id: str, offset: int, source: BinaryIO, length: int) -> dict[str, Any]:
        if length < 0 or length > MAX_CHUNK_SIZE:
            raise ValueError("O bloco precisa ter no máximo 64 MiB.")
        with self._lock:
            metadata = self._load_upload(upload_id)
            part = self._upload_part_path(upload_id)
            current = part.stat().st_size
            if int(offset) != current:
                raise ValueError(f"Posição inesperada. Continue a partir de {current} bytes.")
            if current + length > int(metadata["expectedSize"]):
                raise ValueError("O bloco ultrapassa o tamanho informado do arquivo.")
            chunk_path = self.upload_root / f"{upload_id}.chunk"
            remaining = length
            try:
                with chunk_path.open("wb") as chunk:
                    while remaining:
                        data = source.read(min(1024 * 1024, remaining))
                        if not data:
                            raise ValueError("O bloco terminou antes do tamanho informado.")
                        chunk.write(data)
                        remaining -= len(data)
                with part.open("ab") as destination, chunk_path.open("rb") as chunk:
                    shutil.copyfileobj(chunk, destination, length=1024 * 1024)
            finally:
                chunk_path.unlink(missing_ok=True)
            new_offset = part.stat().st_size
            return {"uploadId": upload_id, "offset": new_offset, "size": int(metadata["expectedSize"])}

    def finish_upload(self, upload_id: str) -> dict[str, Any]:
        with self._lock:
            metadata = self._load_upload(upload_id)
            part = self._upload_part_path(upload_id)
            actual_size = part.stat().st_size
            if actual_size != int(metadata["expectedSize"]):
                raise ValueError(f"Upload incompleto: {actual_size} de {metadata['expectedSize']} bytes.")
            folder_id = str(metadata.get("folderId", ""))
            if folder_id:
                result = self._finish_folder_file(folder_id, metadata, part)
            else:
                item_id = uuid4().hex
                destination = self.root / f"{item_id}.bin"
                self.root.mkdir(parents=True, exist_ok=True)
                part.replace(destination)
                result = self._add_record({
                    "id": item_id, "name": metadata["name"], "type": metadata["type"],
                    "size": actual_size, "kind": "file", "lastModified": metadata["lastModified"],
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                })
            self._upload_metadata_path(upload_id).unlink(missing_ok=True)
            return result

    def cancel_upload(self, upload_id: str) -> bool:
        if not self._valid_id(upload_id):
            return False
        with self._lock:
            paths = [
                self._upload_metadata_path(upload_id), self._upload_part_path(upload_id),
                self.upload_root / f"{upload_id}.chunk",
            ]
            existed = any(path.exists() for path in paths)
            for path in paths:
                path.unlink(missing_ok=True)
            return existed

    def begin_folder(self, *, name: str, expected_files: int, expected_size: int) -> dict[str, Any]:
        file_count = max(0, int(expected_files))
        size = max(0, int(expected_size))
        if file_count > 1_000_000:
            raise ValueError("A pasta informa uma quantidade de arquivos inválida.")
        self.root.mkdir(parents=True, exist_ok=True)
        if size > max(0, shutil.disk_usage(self.root).free - DISK_RESERVE):
            raise ValueError("Não há espaço livre suficiente para receber esta pasta.")
        item_id = uuid4().hex
        record = {
            "id": item_id, "name": Path(name or "Pasta selecionada").name[:240], "type": "inode/directory",
            "size": size, "expectedSize": size, "kind": "folder", "fileCount": file_count,
            "receivedFiles": 0, "uploadedSize": 0, "status": "uploading",
            "lastModified": 0, "createdAt": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            directory = self.folder_root / item_id
            directory.mkdir(parents=True, exist_ok=True)
            self._folder_manifest_path(item_id).write_text("", encoding="utf-8")
            return self._add_record(record)

    def finish_folder(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._find_record(item_id)
            if record.get("kind") != "folder":
                raise ValueError("Item não é uma pasta.")
            manifest = self._load_folder_manifest(item_id)
            received_files = len(manifest["files"])
            uploaded_size = sum(int(item.get("size", 0)) for item in manifest["files"])
            expected_files = int(record.get("fileCount", 0) or 0)
            expected_size = int(record.get("expectedSize", 0) or 0)
            if expected_files and received_files != expected_files:
                raise ValueError(f"Pasta incompleta: {received_files} de {expected_files} arquivos recebidos.")
            if expected_size and uploaded_size != expected_size:
                raise ValueError(f"Pasta incompleta: {uploaded_size} de {expected_size} bytes recebidos.")
            record["receivedFiles"] = received_files
            record["uploadedSize"] = uploaded_size
            record["size"] = record["uploadedSize"]
            record["status"] = "ready"
            self._replace_record(record)
            return record

    def folder_manifest(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            record = self._find_record(item_id)
            if record.get("kind") != "folder":
                raise KeyError("Pasta não encontrada.")
            manifest = self._load_folder_manifest(item_id)
            return {**record, "files": list(manifest["files"])}

    def get_folder_file(self, folder_id: str, file_id: str) -> tuple[dict[str, Any], Path]:
        if not self._valid_id(folder_id) or not self._valid_id(file_id):
            raise KeyError("Arquivo inválido.")
        with self._lock:
            manifest = self._load_folder_manifest(folder_id)
            item = next((entry for entry in manifest["files"] if entry.get("id") == file_id), None)
            path = self.folder_root / folder_id / f"{file_id}.bin"
            if not item or not path.is_file():
                raise KeyError("Arquivo da pasta não encontrado.")
            return item, path

    def _finish_folder_file(self, folder_id: str, metadata: dict[str, Any], part: Path) -> dict[str, Any]:
        manifest = self._load_folder_manifest(folder_id)
        file_id = uuid4().hex
        destination = self.folder_root / folder_id / f"{file_id}.bin"
        destination.parent.mkdir(parents=True, exist_ok=True)
        part.replace(destination)
        item = {
            "id": file_id, "name": metadata["name"], "path": metadata["relativePath"],
            "type": metadata["type"], "size": int(metadata["expectedSize"]),
            "lastModified": metadata["lastModified"],
        }
        with self._folder_manifest_path(folder_id).open("a", encoding="utf-8") as manifest_file:
            manifest_file.write(json.dumps(item, ensure_ascii=False) + "\n")
        record = self._find_record(folder_id)
        record["receivedFiles"] = int(record.get("receivedFiles", 0)) + 1
        record["uploadedSize"] = int(record.get("uploadedSize", 0)) + int(item["size"])
        self._replace_record(record)
        return {**item, "folderId": folder_id}

    def _replace_record(self, record: dict[str, Any]) -> None:
        self._write([record if item.get("id") == record["id"] else item for item in self._load()])

    def _find_record(self, item_id: str) -> dict[str, Any]:
        if not self._valid_id(item_id):
            raise KeyError("Item inválido.")
        record = next((item for item in self._load() if item.get("id") == item_id), None)
        if not record:
            raise KeyError("Item da Drop Zone não encontrado.")
        return dict(record)

    def _load_upload(self, upload_id: str) -> dict[str, Any]:
        if not self._valid_id(upload_id):
            raise KeyError("Upload inválido.")
        try:
            payload = json.loads(self._upload_metadata_path(upload_id).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise KeyError("Upload não encontrado.") from exc
        return payload

    def _load_folder_manifest(self, item_id: str) -> dict[str, Any]:
        if not self._valid_id(item_id):
            raise KeyError("Pasta inválida.")
        path = self._folder_manifest_path(item_id)
        try:
            files = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError) as exc:
            raise KeyError("Conteúdo da pasta não encontrado.") from exc
        if not all(isinstance(item, dict) for item in files):
            raise KeyError("Manifesto da pasta inválido.")
        return {"files": files}

    def _upload_metadata_path(self, upload_id: str) -> Path:
        return self.upload_root / f"{upload_id}.json"

    def _upload_part_path(self, upload_id: str) -> Path:
        return self.upload_root / f"{upload_id}.part"

    def _folder_manifest_path(self, item_id: str) -> Path:
        return self.folder_root / item_id / "manifest.jsonl"

    @staticmethod
    def _safe_relative_path(value: str) -> str:
        path = PurePosixPath(str(value or "arquivo").replace("\\", "/"))
        if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError("Caminho relativo inválido.")
        return "/".join(path.parts)[:1000]

    @staticmethod
    def _valid_id(value: str) -> bool:
        return len(value) == 32 and all(character in "0123456789abcdef" for character in value.lower())

    def history(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._load())

    def get(self, item_id: str) -> tuple[dict[str, Any], Path | None]:
        with self._lock:
            record = self._find_record(item_id)
            path = self.root / f"{item_id}.bin" if record.get("kind") == "file" else None
            if path is not None and not path.is_file():
                raise KeyError("Conteúdo do item não encontrado.")
            return record, path

    def remove(self, item_id: str) -> bool:
        with self._lock:
            items = self._load()
            removed = next((item for item in items if item.get("id") == item_id), None)
            if not removed:
                return False
            self._purge_payload(removed)
            self._write([item for item in items if item.get("id") != item_id])
            return True
