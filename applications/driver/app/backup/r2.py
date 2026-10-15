from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import settings


class R2UnavailableError(RuntimeError):
    pass


class R2IntegrityError(RuntimeError):
    pass


class R2Client:
    def __init__(self) -> None:
        if not settings.r2_enabled:
            raise R2UnavailableError("R2 está desativado. Defina R2_ENABLED=true.")
        missing = [
            name for name, value in {
                "R2_ACCESS_KEY_ID": settings.r2_access_key_id,
                "R2_SECRET_ACCESS_KEY": settings.r2_secret_access_key,
                "R2_BUCKET": settings.r2_bucket,
                "R2_ENDPOINT": settings.r2_endpoint,
            }.items() if not value
        ]
        if missing:
            raise R2UnavailableError("Configuração R2 incompleta: " + ", ".join(missing))
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise R2UnavailableError("Dependência boto3 ausente. Instale requirements-cloud.txt.") from exc
        self.bucket = settings.r2_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name=settings.r2_region,
            config=Config(retries={"max_attempts": 3, "mode": "standard"}),
        )

    @staticmethod
    def key_for(relative_path: str, namespace: str = "files") -> str:
        parts = [p for p in (settings.r2_prefix, namespace, relative_path.strip("/")) if p]
        return "/".join(parts)

    def test_connection(self) -> dict[str, Any]:
        response = self.client.list_objects_v2(Bucket=self.bucket, MaxKeys=1)
        return {"ok": True, "http_status": response.get("ResponseMetadata", {}).get("HTTPStatusCode")}

    def upload_verified(self, local_path: Path, key: str, sha256: str, content_type: str | None = None) -> dict[str, Any]:
        extra: dict[str, Any] = {"Metadata": {"drive2-sha256": sha256}}
        if content_type:
            extra["ContentType"] = content_type
        self.client.upload_file(str(local_path), self.bucket, key, ExtraArgs=extra)
        return self.verify_object(key, sha256, local_path.stat().st_size)

    def verify_object(self, key: str, expected_sha256: str, expected_size: int) -> dict[str, Any]:
        head = self.client.head_object(Bucket=self.bucket, Key=key)
        remote_hash = (head.get("Metadata") or {}).get("drive2-sha256")
        remote_size = int(head.get("ContentLength") or -1)
        if remote_hash != expected_sha256 or remote_size != expected_size:
            raise R2IntegrityError(
                f"Validação remota falhou para {key}: size={remote_size}, sha256={remote_hash!r}."
            )
        return {"key": key, "size": remote_size, "sha256": remote_hash, "etag": head.get("ETag")}

    def download_verified(self, key: str, destination: Path, expected_sha256: str, expected_size: int | None = None) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(destination))
        import hashlib
        digest = hashlib.sha256()
        with destination.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        actual_hash = digest.hexdigest()
        if actual_hash != expected_sha256:
            destination.unlink(missing_ok=True)
            raise R2IntegrityError("SHA-256 do arquivo restaurado não corresponde ao índice.")
        if expected_size is not None and destination.stat().st_size != expected_size:
            destination.unlink(missing_ok=True)
            raise R2IntegrityError("Tamanho do arquivo restaurado não corresponde ao índice.")
        return destination

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def head(self, key: str) -> dict[str, Any]:
        return self.client.head_object(Bucket=self.bucket, Key=key)
