from __future__ import annotations

import logging
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.auth.security import create_session, verify_password
from app.backup.r2 import R2Client
from app.config import settings
from app.database.backup_repository import delete_policy, list_policies, path_is_protected, set_policy
from app.database.db import db_session
from app.database.email_repository import get_message_by_id, list_messages
from app.database.log_repository import list_logs
from app.database.repository import (
    get_file,
    list_favorites,
    list_recent,
    mark_path_unavailable,
    remap_path_prefix,
    search as search_repository,
    set_favorite,
    set_sync_state,
    stats as repository_stats,
)
from app.database.sync_repository import enqueue, list_history, list_queue
from app.database.trash_repository import add_trash, delete_trash, get_trash, list_trash
from app.email.gmail import GmailService, GmailUnavailableError
from app.files.indexer import index_one, index_subtree, index_tree
from app.files.service import FileConflictError, FileService, InvalidPathError, TrashService
from app.sync.service import SyncService, restore_from_cloud

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
files = FileService(settings.storage_root)
trash = TrashService(files, settings.trash_root)
sync_service = SyncService(files)


class DirectoryCreate(BaseModel):
    path: str = Field(min_length=1, max_length=1024)


class RenameRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    new_name: str = Field(min_length=1, max_length=255)


class MoveRequest(BaseModel):
    source: str = Field(min_length=1, max_length=1024)
    destination_dir: str = Field(default="", max_length=1024)


class FavoriteRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)
    favorite: bool


class BackupPolicyRequest(BaseModel):
    path_prefix: str = Field(default="", max_length=1024)
    enabled: bool = True


class RestoreRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1024)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=500)


class GmailRunRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=500)


def _raise_for_file_error(exc: Exception) -> None:
    if isinstance(exc, InvalidPathError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, FileConflictError) or isinstance(exc, FileExistsError):
        raise HTTPException(status_code=409, detail="Já existe um item com esse nome no destino.") from exc
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Arquivo ou pasta não encontrado.") from exc
    if isinstance(exc, NotADirectoryError):
        raise HTTPException(status_code=400, detail="O caminho informado não é uma pasta.") from exc
    if isinstance(exc, OSError):
        raise HTTPException(status_code=507, detail=str(exc)) from exc
    raise exc


def _db_item(relative_path: str) -> dict[str, Any] | None:
    with db_session() as conn:
        return get_file(conn, relative_path)


def _enrich(item: dict[str, Any]) -> dict[str, Any]:
    stored = _db_item(item["relative_path"])
    if not stored:
        return item
    for key in ("sha256", "local_available", "cloud_available", "sync_status", "last_backup", "cloud_key", "favorite", "error_message"):
        item[key] = stored.get(key)
    return item


def _db_prefix_conflict(new_prefix: str, old_prefix: str | None = None) -> bool:
    new_prefix = new_prefix.strip("/")
    old_prefix = (old_prefix or "").strip("/")
    with db_session() as conn:
        rows = conn.execute(
            "SELECT relative_path FROM files WHERE relative_path=? OR relative_path LIKE ?",
            (new_prefix, f"{new_prefix}/%"),
        ).fetchall()
    if not rows:
        return False
    if not old_prefix:
        return True
    return any(not (row["relative_path"] == old_prefix or row["relative_path"].startswith(old_prefix + "/")) for row in rows)


def _queue_after_path_change(prefix: str) -> None:
    prefix = prefix.strip("/")
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id,relative_path,is_directory FROM files WHERE relative_path=? OR relative_path LIKE ?",
            (prefix, f"{prefix}/%"),
        ).fetchall()
        for row in rows:
            if not row["is_directory"] and path_is_protected(conn, row["relative_path"]):
                enqueue(conn, int(row["id"]))


def _normalize_restored_subtree(prefix: str) -> None:
    prefix = prefix.strip("/")
    with db_session() as conn:
        rows = conn.execute(
            "SELECT id,relative_path,is_directory,cloud_available FROM files WHERE relative_path=? OR relative_path LIKE ?",
            (prefix, f"{prefix}/%"),
        ).fetchall()
        for row in rows:
            if row["is_directory"]:
                continue
            if row["cloud_available"]:
                conn.execute("UPDATE files SET sync_status='SYNCED', error_message=NULL WHERE id=?", (row["id"],))
            elif path_is_protected(conn, row["relative_path"]):
                enqueue(conn, int(row["id"]))
            else:
                conn.execute("UPDATE files SET sync_status='LOCAL_ONLY', error_message=NULL WHERE id=?", (row["id"],))


@router.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": settings.version,
        "r2_enabled": settings.r2_enabled,
        "gmail_enabled": settings.gmail_enabled,
        "auth_enabled": settings.auth_enabled,
        "tailscale_only": settings.tailscale_only,
    }


@router.post("/auth/login")
def login(payload: LoginRequest, response: Response) -> dict[str, Any]:
    if not settings.auth_enabled:
        return {"authenticated": True, "auth_enabled": False}
    if not settings.auth_password_hash or not settings.auth_secret:
        raise HTTPException(status_code=503, detail="Autenticação habilitada, mas senha/secret não configurados.")
    if payload.username != settings.auth_username or not verify_password(payload.password, settings.auth_password_hash):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")
    response.set_cookie(
        "drive2_session",
        create_session(payload.username),
        httponly=True,
        samesite="strict",
        secure=settings.auth_cookie_secure,
        max_age=settings.auth_session_hours * 3600,
    )
    return {"authenticated": True, "auth_enabled": True}


@router.post("/auth/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie("drive2_session")
    return {"authenticated": False}


@router.get("/storage")
def storage() -> dict[str, int]:
    return files.storage_usage()


@router.get("/dashboard")
def dashboard() -> dict[str, Any]:
    with db_session() as conn:
        data = repository_stats(conn)
        data["queue"] = list_queue(conn, 20)
    data["storage"] = files.storage_usage()
    data["r2_enabled"] = settings.r2_enabled
    data["gmail_enabled"] = settings.gmail_enabled
    return data


@router.get("/files")
def list_files(path: str = Query(default="", max_length=1024)) -> dict[str, Any]:
    try:
        items = files.list_dir(path)
        result = []
        for item in items:
            stored = _db_item(item["relative_path"])
            if not stored:
                index_one(files, files.resolve(item["relative_path"]), calculate_hash=True, queue_backup=True)
            result.append(_enrich(item))
        return {"path": path.strip("/"), "items": result}
    except Exception as exc:
        _raise_for_file_error(exc)
        raise


@router.get("/files/cloud")
def cloud_files(limit: int = Query(default=500, ge=1, le=2000)) -> dict[str, Any]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM files WHERE cloud_available=1 ORDER BY local_available ASC, relative_path COLLATE NOCASE LIMIT ?",
            (limit,),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@router.get("/recent")
def recent(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    with db_session() as conn:
        return {"items": list_recent(conn, limit)}


@router.get("/favorites")
def favorites(limit: int = Query(default=500, ge=1, le=1000)) -> dict[str, Any]:
    with db_session() as conn:
        return {"items": list_favorites(conn, limit)}


@router.patch("/favorites")
def favorite(payload: FavoriteRequest) -> dict[str, Any]:
    target = files.resolve(payload.path)
    if target.exists():
        index_one(files, target, calculate_hash=False, queue_backup=False)
    with db_session() as conn:
        item = set_favorite(conn, payload.path.strip("/"), payload.favorite)
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
    return item


@router.post("/directories", status_code=201)
def create_directory(payload: DirectoryCreate) -> dict[str, Any]:
    try:
        path = files.create_directory(payload.path)
        return _enrich(index_one(files, path))
    except Exception as exc:
        _raise_for_file_error(exc)
        raise


@router.post("/upload", status_code=201)
async def upload_file(path: str = Query(default="", max_length=1024), file: UploadFile = File(...)) -> dict[str, Any]:
    filename = Path(file.filename or "upload.bin").name
    if filename in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
    try:
        folder = files.resolve(path)
        if not folder.is_dir():
            raise NotADirectoryError(path)
        destination = files.resolve(files.relative(folder / filename))
        if destination.exists():
            raise FileConflictError(filename)
        temp = settings.temp_root / f"upload-{secrets.token_hex(8)}-{filename}.part"
        settings.temp_root.mkdir(parents=True, exist_ok=True)
        max_bytes = settings.max_upload_mb * 1024 * 1024
        written = 0
        try:
            with temp.open("wb") as out:
                while chunk := await file.read(1024 * 1024):
                    written += len(chunk)
                    if written > max_bytes:
                        raise HTTPException(status_code=413, detail=f"Upload excede {settings.max_upload_mb} MB.")
                    files.ensure_space_for(len(chunk))
                    out.write(chunk)
            destination.parent.mkdir(parents=True, exist_ok=True)
            files.commit_upload(temp, destination)
        finally:
            await file.close()
            temp.unlink(missing_ok=True)
        return _enrich(index_one(files, destination, calculate_hash=True, queue_backup=True))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Falha no upload")
        _raise_for_file_error(exc)
        raise


@router.get("/download")
def download(path: str = Query(min_length=1, max_length=1024)) -> FileResponse:
    try:
        target = files.resolve(path)
        if not target.exists():
            raise FileNotFoundError(path)
        if not target.is_file():
            raise HTTPException(status_code=400, detail="Somente arquivos podem ser baixados.")
        return FileResponse(target, filename=target.name)
    except HTTPException:
        raise
    except Exception as exc:
        _raise_for_file_error(exc)
        raise


@router.patch("/files/rename")
def rename(payload: RenameRequest) -> dict[str, Any]:
    try:
        old = payload.path.strip("/")
        if not payload.new_name or payload.new_name in {".", ".."} or "/" in payload.new_name or "\\" in payload.new_name:
            raise InvalidPathError("Nome inválido.")
        source = files.resolve(old)
        if not source.exists():
            raise FileNotFoundError(old)
        new = files.relative(source.with_name(payload.new_name))
        if _db_prefix_conflict(new, old):
            raise FileConflictError(new)
        destination = files.rename(payload.path, payload.new_name)
        with db_session() as conn:
            remap_path_prefix(conn, old, new)
        index_subtree(files, destination)
        _queue_after_path_change(new)
        return _enrich(files.info(destination))
    except Exception as exc:
        _raise_for_file_error(exc)
        raise


@router.patch("/files/move")
def move(payload: MoveRequest) -> dict[str, Any]:
    try:
        old = payload.source.strip("/")
        source = files.resolve(old)
        if not source.exists():
            raise FileNotFoundError(old)
        destination_folder = files.resolve(payload.destination_dir)
        if not destination_folder.is_dir():
            raise NotADirectoryError(payload.destination_dir)
        new = files.relative(destination_folder / source.name)
        if _db_prefix_conflict(new, old):
            raise FileConflictError(new)
        destination = files.move(payload.source, payload.destination_dir)
        with db_session() as conn:
            remap_path_prefix(conn, old, new)
        index_subtree(files, destination)
        _queue_after_path_change(new)
        return _enrich(files.info(destination))
    except Exception as exc:
        _raise_for_file_error(exc)
        raise


@router.delete("/files")
def delete(path: str = Query(min_length=1, max_length=1024)) -> dict[str, Any]:
    try:
        normalized = path.strip("/")
        target = files.resolve(normalized)
        is_directory = target.is_dir()
        _, trash_name = trash.move_to_trash(normalized)
        with db_session() as conn:
            add_trash(conn, normalized, trash_name, is_directory)
            mark_path_unavailable(conn, normalized)
        return {"trashed": normalized}
    except Exception as exc:
        _raise_for_file_error(exc)
        raise


@router.get("/trash")
def trash_list(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    with db_session() as conn:
        return {"items": list_trash(conn, limit)}


@router.post("/trash/{entry_id}/restore")
def trash_restore(entry_id: int) -> dict[str, Any]:
    with db_session() as conn:
        entry = get_trash(conn, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entrada da lixeira não encontrada.")
    try:
        destination = trash.restore(entry["trash_path"], entry["original_path"])
        index_subtree(files, destination)
        _normalize_restored_subtree(entry["original_path"])
        with db_session() as conn:
            delete_trash(conn, entry_id)
        return {"restored": entry["original_path"]}
    except Exception as exc:
        _raise_for_file_error(exc)
        raise


@router.delete("/trash/{entry_id}")
def trash_purge(entry_id: int) -> dict[str, Any]:
    with db_session() as conn:
        entry = get_trash(conn, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entrada da lixeira não encontrada.")
    try:
        trash.purge(entry["trash_path"])
        with db_session() as conn:
            delete_trash(conn, entry_id)
        return {"purged": entry["original_path"]}
    except Exception as exc:
        _raise_for_file_error(exc)
        raise


@router.get("/search")
def search(q: str = Query(min_length=1, max_length=255), limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    with db_session() as conn:
        return {"query": q, "items": search_repository(conn, q, limit)}


@router.post("/index/rebuild")
def rebuild_index() -> dict[str, Any]:
    return index_tree(files)


@router.get("/backup/policies")
def backup_policies() -> dict[str, Any]:
    with db_session() as conn:
        return {"items": list_policies(conn)}


@router.put("/backup/policies")
def backup_policy_set(payload: BackupPolicyRequest) -> dict[str, Any]:
    with db_session() as conn:
        policy = set_policy(conn, payload.path_prefix, payload.enabled)
        queued = 0
        if payload.enabled:
            prefix = payload.path_prefix.strip("/")
            if prefix:
                rows = conn.execute(
                    "SELECT id FROM files WHERE is_directory=0 AND local_available=1 AND (relative_path=? OR relative_path LIKE ?)",
                    (prefix, f"{prefix}/%"),
                ).fetchall()
            else:
                rows = conn.execute("SELECT id FROM files WHERE is_directory=0 AND local_available=1").fetchall()
            for row in rows:
                enqueue(conn, int(row["id"]))
                queued += 1
    policy["queued"] = queued
    return policy


@router.delete("/backup/policies")
def backup_policy_delete(path_prefix: str = Query(default="", max_length=1024)) -> dict[str, str]:
    with db_session() as conn:
        delete_policy(conn, path_prefix)
    return {"deleted": path_prefix.strip("/")}


@router.get("/backup/queue")
def backup_queue(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    with db_session() as conn:
        return {"items": list_queue(conn, limit)}


@router.get("/backup/history")
def backup_history(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    with db_session() as conn:
        return {"items": list_history(conn, limit)}


@router.post("/backup/run-one")
def backup_run_one() -> dict[str, Any]:
    return {"processed": sync_service.process_one()}


@router.get("/backup/test")
def backup_test() -> dict[str, Any]:
    try:
        return R2Client().test_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/backup/restore")
def backup_restore(payload: RestoreRequest) -> dict[str, Any]:
    normalized = payload.path.strip("/")
    prior = _db_item(normalized)
    try:
        destination = restore_from_cloud(files, normalized)
        indexed = index_one(files, destination, calculate_hash=True, queue_backup=False)
        if prior and prior.get("cloud_available") and prior.get("cloud_key"):
            with db_session() as conn:
                current = get_file(conn, normalized)
                if current:
                    set_sync_state(
                        conn, int(current["id"]), "SYNCED", cloud_available=True,
                        cloud_key=prior["cloud_key"], last_backup=prior.get("last_backup"), error_message=None,
                    )
        return {"restored": normalized, "sha256": indexed.get("sha256")}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        _raise_for_file_error(exc)
        raise


@router.get("/logs")
def logs(limit: int = Query(default=200, ge=1, le=1000)) -> dict[str, Any]:
    with db_session() as conn:
        return {"items": list_logs(conn, limit)}


@router.get("/settings")
def public_settings() -> dict[str, Any]:
    return {
        "version": settings.version,
        "scan_interval_seconds": settings.scan_interval_seconds,
        "sync_interval_seconds": settings.sync_interval_seconds,
        "max_upload_mb": settings.max_upload_mb,
        "auth_enabled": settings.auth_enabled,
        "tailscale_only": settings.tailscale_only,
        "r2_enabled": settings.r2_enabled,
        "r2_bucket": settings.r2_bucket if settings.r2_enabled else "",
        "gmail_enabled": settings.gmail_enabled,
        "gmail_archive_after_days": settings.gmail_archive_after_days,
        "gmail_max_message_mb": settings.gmail_max_message_mb,
        "gmail_trash_after_backup": settings.gmail_trash_after_backup,
    }


@router.get("/emails")
def emails(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    with db_session() as conn:
        return {"items": list_messages(conn, limit)}


@router.get("/emails/{email_id}/download")
def email_download(email_id: int) -> FileResponse:
    with db_session() as conn:
        item = get_message_by_id(conn, email_id)
    if not item:
        raise HTTPException(status_code=404, detail="E-mail arquivado não encontrado.")
    target = (settings.emails_root / item["eml_path"]).resolve()
    try:
        target.relative_to(settings.emails_root.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Caminho de e-mail inválido.") from exc
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Arquivo .eml não encontrado no armazenamento local.")
    return FileResponse(target, media_type="message/rfc822", filename=f"{item['gmail_message_id']}.eml")


@router.get("/gmail/status")
def gmail_status() -> dict[str, Any]:
    try:
        return GmailService().status()
    except GmailUnavailableError:
        return {
            "enabled": settings.gmail_enabled,
            "authenticated": settings.gmail_token_path.exists(),
            "archive_after_days": settings.gmail_archive_after_days,
        }


@router.post("/gmail/archive")
def gmail_archive(payload: GmailRunRequest) -> dict[str, Any]:
    try:
        return GmailService().run_archive(payload.limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
