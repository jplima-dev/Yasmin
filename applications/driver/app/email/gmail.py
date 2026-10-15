from __future__ import annotations

import base64
import hashlib
import mimetypes
import os
import re
import secrets
import shutil
import time
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from app.backup.r2 import R2Client
from app.config import settings
from app.database.db import db_session
from app.database.email_repository import (
    get_message,
    insert_attachment,
    insert_message,
    list_attachments,
    mark_backed_up,
    mark_trashed,
)
from app.database.log_repository import add_log

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailUnavailableError(RuntimeError):
    pass


def _google_imports():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise GmailUnavailableError("Bibliotecas do Gmail ausentes. Instale requirements-gmail.txt.") from exc
    return Request, Credentials, InstalledAppFlow, build


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_filename(name: str, fallback: str = "attachment.bin") -> str:
    name = Path(name or fallback).name
    name = re.sub(r"[\x00-\x1f<>:\"/\\|?*]+", "_", name).strip(" .")
    return name or fallback


class GmailService:
    def __init__(self) -> None:
        if not settings.gmail_enabled:
            raise GmailUnavailableError("Gmail está desativado. Defina GMAIL_ENABLED=true.")

    def authenticate(self, open_browser: bool = True) -> None:
        Request, Credentials, InstalledAppFlow, _ = _google_imports()
        creds = None
        if settings.gmail_token_path.exists():
            creds = Credentials.from_authorized_user_file(str(settings.gmail_token_path), SCOPES)
        if creds and creds.valid:
            return
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not settings.gmail_credentials_path.exists():
                raise GmailUnavailableError(f"Credencial OAuth não encontrada: {settings.gmail_credentials_path}")
            flow = InstalledAppFlow.from_client_secrets_file(str(settings.gmail_credentials_path), SCOPES)
            creds = flow.run_local_server(port=0, open_browser=open_browser)
        settings.gmail_token_path.parent.mkdir(parents=True, exist_ok=True)
        settings.gmail_token_path.write_text(creds.to_json(), encoding="utf-8")
        try:
            os.chmod(settings.gmail_token_path, 0o600)
        except OSError:
            pass

    def client(self):
        Request, Credentials, _, build = _google_imports()
        if not settings.gmail_token_path.exists():
            raise GmailUnavailableError("Gmail ainda não foi autenticado. Execute `python -m app.email.cli auth`.")
        creds = Credentials.from_authorized_user_file(str(settings.gmail_token_path), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            settings.gmail_token_path.write_text(creds.to_json(), encoding="utf-8")
        if not creds.valid:
            raise GmailUnavailableError("Token OAuth inválido. Autentique novamente.")
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def status(self) -> dict[str, Any]:
        return {
            "enabled": settings.gmail_enabled,
            "authenticated": settings.gmail_token_path.exists(),
            "archive_after_days": settings.gmail_archive_after_days,
            "max_message_mb": settings.gmail_max_message_mb,
            "protect_starred": settings.gmail_protect_starred,
            "protect_important": settings.gmail_protect_important,
            "trash_after_backup": settings.gmail_trash_after_backup,
        }

    def archive_candidates(self, max_results: int = 100) -> list[dict[str, str]]:
        service = self.client()
        terms = [f"older_than:{settings.gmail_archive_after_days}d", "-in:trash"]
        if settings.gmail_protect_starred:
            terms.append("-is:starred")
        if settings.gmail_protect_important:
            terms.append("-is:important")
        query = " ".join(terms)
        result = service.users().messages().list(userId="me", q=query, maxResults=min(max_results, 500)).execute()
        return result.get("messages", [])

    def _existing_local_files(self, existing: dict[str, Any], attachments: list[dict[str, Any]]) -> tuple[Path, list[tuple[dict[str, Any], Path]]]:
        eml_path = (settings.emails_root / existing["eml_path"]).resolve()
        try:
            eml_path.relative_to(settings.emails_root.resolve())
        except ValueError as exc:
            raise GmailUnavailableError("Caminho .eml inválido no índice.") from exc
        if not eml_path.is_file() or sha256_bytes(eml_path.read_bytes()) != existing["eml_sha256"]:
            raise GmailUnavailableError("A cópia local .eml existente está ausente ou falhou no SHA-256.")
        resolved: list[tuple[dict[str, Any], Path]] = []
        for attachment in attachments:
            path = (settings.attachments_root / attachment["relative_path"]).resolve()
            try:
                path.relative_to(settings.attachments_root.resolve())
            except ValueError as exc:
                raise GmailUnavailableError("Caminho de anexo inválido no índice.") from exc
            if not path.is_file() or path.stat().st_size != int(attachment["size"]) or sha256_bytes(path.read_bytes()) != attachment["sha256"]:
                raise GmailUnavailableError(f"Anexo local ausente ou inválido: {attachment['filename']}")
            resolved.append((attachment, path))
        return eml_path, resolved

    def _backup_existing(self, existing: dict[str, Any], attachments: list[dict[str, Any]], eml_path: Path, resolved: list[tuple[dict[str, Any], Path]]) -> bool:
        if not settings.r2_enabled:
            return bool(existing.get("backed_up"))
        r2 = R2Client()
        eml_key = r2.key_for(eml_path.name, "emails")
        if existing.get("backed_up"):
            # Revalidate immediately before any destructive Gmail action.
            r2.verify_object(eml_key, existing["eml_sha256"], int(existing["size"]))
            for attachment, _ in resolved:
                key = r2.key_for(f"{existing['gmail_message_id']}/{attachment['filename']}", "email-attachments")
                r2.verify_object(key, attachment["sha256"], int(attachment["size"]))
            return True
        r2.upload_verified(eml_path, eml_key, existing["eml_sha256"], "message/rfc822")
        for attachment, path in resolved:
            key = r2.key_for(f"{existing['gmail_message_id']}/{attachment['filename']}", "email-attachments")
            r2.upload_verified(path, key, attachment["sha256"], attachment.get("mime_type"))
        with db_session() as conn:
            mark_backed_up(conn, int(existing["id"]), True)
            add_log(conn, "INFO", "gmail.backup", f"Backup R2 concluído para e-mail já arquivado: {existing['gmail_message_id']}")
        return True

    def archive_message(self, message_id: str) -> dict[str, Any]:
        with db_session() as conn:
            existing = get_message(conn, message_id)
            existing_attachments = list_attachments(conn, int(existing["id"])) if existing else []

        if existing:
            eml_path, resolved = self._existing_local_files(existing, existing_attachments)
            backed_up = self._backup_existing(existing, existing_attachments, eml_path, resolved)
            trashed = bool(existing.get("trashed_in_gmail"))
            if settings.gmail_trash_after_backup and not trashed:
                if not settings.r2_enabled or not backed_up:
                    return {
                        "status": "already_archived_local", "message_id": message_id,
                        "backed_up": backed_up, "trashed_in_gmail": False,
                        "detail": "Lixeira não executada: R2 validado é obrigatório para esta configuração.",
                    }
                # _backup_existing revalidates remote objects when backed_up was already true.
                gmail = self.client()
                gmail.users().messages().trash(userId="me", id=message_id).execute()
                with db_session() as conn:
                    mark_trashed(conn, int(existing["id"]), True)
                    add_log(conn, "INFO", "gmail.trash", f"Movido para a lixeira do Gmail: {message_id}")
                trashed = True
                return {"status": "trashed_after_validation", "message_id": message_id, "backed_up": True, "trashed_in_gmail": True}
            return {"status": "already_archived", "message_id": message_id, "backed_up": backed_up, "trashed_in_gmail": trashed}

        gmail = self.client()
        # Read small metadata first so protected or oversized messages do not need
        # to be downloaded into RAM on a limited Android device.
        metadata = gmail.users().messages().get(userId="me", id=message_id, format="metadata").execute()
        labels = set(metadata.get("labelIds", []))
        if settings.gmail_protect_starred and "STARRED" in labels:
            return {"status": "protected_starred", "message_id": message_id}
        if settings.gmail_protect_important and "IMPORTANT" in labels:
            return {"status": "protected_important", "message_id": message_id}
        size_estimate = int(metadata.get("sizeEstimate") or 0)
        max_bytes = settings.gmail_max_message_mb * 1024 * 1024
        if size_estimate > max_bytes:
            return {
                "status": "skipped_too_large", "message_id": message_id,
                "size_estimate": size_estimate, "limit_mb": settings.gmail_max_message_mb,
            }

        resource = gmail.users().messages().get(userId="me", id=message_id, format="raw").execute()
        labels = set(resource.get("labelIds", labels))
        raw_value = resource.get("raw")
        if not raw_value:
            raise GmailUnavailableError("Gmail não retornou o conteúdo RAW da mensagem.")
        raw_value += "=" * (-len(raw_value) % 4)
        raw = base64.urlsafe_b64decode(raw_value.encode())
        eml_hash = sha256_bytes(raw)
        settings.emails_root.mkdir(parents=True, exist_ok=True)
        settings.attachments_root.mkdir(parents=True, exist_ok=True)
        eml_path = settings.emails_root / f"{message_id}.eml"
        temp = settings.emails_root / f".{message_id}.{secrets.token_hex(8)}.eml.tmp"
        temp.write_bytes(raw)
        if sha256_bytes(temp.read_bytes()) != eml_hash:
            temp.unlink(missing_ok=True)
            raise IOError("Falha na validação local do .eml.")
        temp.replace(eml_path)

        parsed = BytesParser(policy=policy.default).parsebytes(raw)
        sender = str(parsed.get("From", ""))
        recipients = str(parsed.get("To", ""))
        subject = str(parsed.get("Subject", "(sem assunto)"))
        msg_date = None
        if parsed.get("Date"):
            try:
                msg_date = parsedate_to_datetime(str(parsed.get("Date"))).timestamp()
            except Exception:
                msg_date = None
        internal_ms = int(resource.get("internalDate") or 0)
        internal_date = internal_ms / 1000 if internal_ms else None
        archived_at = time.time()

        attachments: list[dict[str, Any]] = []
        attach_dir = settings.attachments_root / message_id
        # If a prior attempt failed before the DB transaction, this directory may
        # contain unindexed partial remnants. It is private to this message ID.
        if attach_dir.exists():
            shutil.rmtree(attach_dir)
        for index, part in enumerate(parsed.iter_attachments(), start=1):
            payload = part.get_payload(decode=True) or b""
            filename = safe_filename(part.get_filename() or f"attachment-{index}.bin")
            attach_dir.mkdir(parents=True, exist_ok=True)
            destination = attach_dir / filename
            if destination.exists():
                destination = attach_dir / f"{index}-{filename}"
            destination.write_bytes(payload)
            digest = sha256_bytes(payload)
            if sha256_bytes(destination.read_bytes()) != digest:
                destination.unlink(missing_ok=True)
                raise IOError(f"Falha na validação do anexo {filename}.")
            attachments.append({
                "filename": destination.name,
                "relative_path": destination.relative_to(settings.attachments_root).as_posix(),
                "mime_type": part.get_content_type() or mimetypes.guess_type(destination.name)[0],
                "size": len(payload),
                "sha256": digest,
                "absolute_path": destination,
            })

        backed_up = False
        if settings.r2_enabled:
            r2 = R2Client()
            r2.upload_verified(eml_path, r2.key_for(eml_path.name, "emails"), eml_hash, "message/rfc822")
            for attachment in attachments:
                key = r2.key_for(f"{message_id}/{attachment['filename']}", "email-attachments")
                r2.upload_verified(
                    attachment["absolute_path"], key, attachment["sha256"], attachment.get("mime_type")
                )
            backed_up = True

        with db_session() as conn:
            email_id = insert_message(conn, {
                "gmail_message_id": message_id,
                "thread_id": resource.get("threadId"),
                "sender": sender,
                "recipients": recipients,
                "subject": subject,
                "message_date": msg_date,
                "internal_date": internal_date,
                "label_ids": sorted(labels),
                "eml_path": eml_path.relative_to(settings.emails_root).as_posix(),
                "eml_sha256": eml_hash,
                "size": len(raw),
                "backed_up": backed_up,
                "trashed_in_gmail": False,
                "archived_at": archived_at,
            })
            for attachment in attachments:
                insert_attachment(conn, email_id, attachment)
            add_log(conn, "INFO", "gmail.archive", f"Arquivado localmente: {message_id} {subject}")

        trashed = False
        if settings.gmail_trash_after_backup and backed_up:
            # All objects were individually HEAD-validated by upload_verified above.
            gmail.users().messages().trash(userId="me", id=message_id).execute()
            trashed = True
            with db_session() as conn:
                mark_trashed(conn, email_id, True)
                add_log(conn, "INFO", "gmail.trash", f"Movido para a lixeira do Gmail: {message_id}")

        return {
            "status": "archived",
            "message_id": message_id,
            "subject": subject,
            "attachments": len(attachments),
            "backed_up": backed_up,
            "trashed_in_gmail": trashed,
        }

    def run_archive(self, max_results: int = 100) -> dict[str, Any]:
        results = []
        for item in self.archive_candidates(max_results=max_results):
            try:
                results.append(self.archive_message(item["id"]))
            except Exception as exc:
                results.append({"status": "error", "message_id": item.get("id"), "error": str(exc)})
        return {
            "checked": len(results),
            "archived": sum(1 for r in results if r.get("status") == "archived"),
            "resumed": sum(1 for r in results if r.get("status") in {"trashed_after_validation", "already_archived", "already_archived_local"}),
            "trashed": sum(1 for r in results if r.get("trashed_in_gmail") or r.get("trashed")),
            "skipped": sum(1 for r in results if str(r.get("status", "")).startswith(("protected_", "skipped_"))),
            "results": results,
        }
