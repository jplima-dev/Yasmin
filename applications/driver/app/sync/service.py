from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.backup.r2 import R2Client, R2IntegrityError, R2UnavailableError
from app.config import settings
from app.database.db import db_session
from app.database.log_repository import add_log
from app.database.repository import update_hash
from app.database.sync_repository import mark_error, mark_success, mark_uploading, next_due
from app.files.service import FileService

logger = logging.getLogger(__name__)


class SyncService:
    def __init__(self, files: FileService):
        self.files = files

    def process_one(self) -> bool:
        with db_session() as conn:
            item = next_due(conn)
            if not item:
                return False
            history_id = mark_uploading(conn, item["id"], item["file_id"])

        try:
            if not item["local_available"]:
                raise FileNotFoundError("Arquivo local indisponível; não é possível enviar ao R2.")
            local = self.files.resolve(item["relative_path"])
            if not local.is_file():
                raise FileNotFoundError(item["relative_path"])
            # Hash immediately before upload and verify again afterwards. This prevents
            # a file changed mid-transfer from being incorrectly marked as protected.
            stat_before = local.stat()
            sha256_before = self.files.hash_file(local)
            if item.get("sha256") != sha256_before:
                with db_session() as conn:
                    update_hash(conn, item["relative_path"], sha256_before)
                    conn.execute(
                        "UPDATE files SET size=?, modified_at=?, cloud_available=0 WHERE id=?",
                        (stat_before.st_size, stat_before.st_mtime, item["file_id"]),
                    )
            r2 = R2Client()
            key = r2.key_for(item["relative_path"])
            r2.upload_verified(local, key, sha256_before, item.get("mime_type"))
            stat_after = local.stat()
            sha256_after = self.files.hash_file(local)
            if stat_after.st_size != stat_before.st_size or sha256_after != sha256_before:
                with db_session() as conn:
                    update_hash(conn, item["relative_path"], sha256_after)
                    conn.execute(
                        "UPDATE files SET size=?, modified_at=?, cloud_available=0 WHERE id=?",
                        (stat_after.st_size, stat_after.st_mtime, item["file_id"]),
                    )
                raise R2IntegrityError("Arquivo mudou durante o upload; uma nova tentativa será feita.")
            with db_session() as conn:
                mark_success(conn, item["id"], history_id, item["file_id"], key)
                add_log(conn, "INFO", "sync.upload", f"Backup validado: {item['relative_path']}")
            return True
        except Exception as exc:
            logger.exception("Falha de sincronização para %s", item["relative_path"])
            with db_session() as conn:
                mark_error(conn, item["id"], history_id, item["file_id"], str(exc), settings.sync_max_retries)
                add_log(conn, "ERROR", "sync.upload", f"{item['relative_path']}: {exc}")
            return True

    async def run_forever(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                processed = await asyncio.to_thread(self.process_one)
            except Exception:
                logger.exception("Erro inesperado no worker de sincronização")
                processed = False
            delay = 1 if processed else settings.sync_interval_seconds
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass


def restore_from_cloud(files: FileService, relative_path: str) -> Path:
    from app.database.repository import get_file

    with db_session() as conn:
        item = get_file(conn, relative_path)
    if not item or not item.get("cloud_available") or not item.get("cloud_key") or not item.get("sha256"):
        raise R2UnavailableError("Não existe cópia remota validada para esse arquivo.")
    destination = files.resolve(relative_path)
    if destination.exists():
        raise FileExistsError(relative_path)
    import secrets
    temp = settings.temp_root / f".{destination.name}.{secrets.token_hex(8)}.restore"
    r2 = R2Client()
    r2.download_verified(item["cloud_key"], temp, item["sha256"], int(item["size"]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp.replace(destination)
    return destination
