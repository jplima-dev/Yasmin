from __future__ import annotations

import asyncio
import ipaddress
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.auth.security import verify_session
from app.config import PROJECT_ROOT, settings
from app.database.db import db_session, init_db
from app.database.log_repository import add_log
from app.files.indexer import index_tree
from app.files.service import FileService
from app.logging_config import configure_logging
from app.sync.scanner import scan_forever
from app.sync.service import SyncService

configure_logging(settings.log_level, PROJECT_ROOT)
files = FileService(settings.storage_root)
sync_service = SyncService(files)
WEB_ROOT = PROJECT_ROOT / "web"
TAILSCALE_V4 = ipaddress.ip_network("100.64.0.0/10")
TAILSCALE_V6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")


def source_is_allowed(host: str | None) -> bool:
    if not settings.tailscale_only:
        return True
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    return ip.is_loopback or ip in TAILSCALE_V4 or ip in TAILSCALE_V6


@asynccontextmanager
async def lifespan(_: FastAPI):
    for folder in (
        settings.storage_root,
        settings.temp_root,
        settings.trash_root,
        settings.emails_root,
        settings.attachments_root,
        PROJECT_ROOT / "logs",
        PROJECT_ROOT / "config",
    ):
        folder.mkdir(parents=True, exist_ok=True)
    if settings.auth_enabled and (not settings.auth_password_hash or not settings.auth_secret):
        raise RuntimeError(
            "DRIVE2_AUTH_ENABLED=true exige DRIVE2_AUTH_PASSWORD_HASH e DRIVE2_AUTH_SECRET. "
            "Veja docs/SECURITY.md."
        )
    init_db()
    files.touch_inbox()
    result = await asyncio.to_thread(index_tree, files)
    with db_session() as conn:
        add_log(conn, "INFO", "server.start", f"Drive2 {settings.version} iniciado; índice={result}")

    stop = asyncio.Event()
    tasks = [asyncio.create_task(scan_forever(files, stop), name="drive2-scanner")]
    if settings.r2_enabled:
        tasks.append(asyncio.create_task(sync_service.run_forever(stop), name="drive2-sync"))
    try:
        yield
    finally:
        stop.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        with db_session() as conn:
            add_log(conn, "INFO", "server.stop", "Drive2 encerrado")


app = FastAPI(title="InkDriver", version=settings.version, lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory=WEB_ROOT), name="static")


@app.middleware("http")
async def access_middleware(request: Request, call_next):
    client_host = request.client.host if request.client else None
    if not source_is_allowed(client_host):
        return JSONResponse({"detail": "Acesso permitido apenas via localhost/Tailscale."}, status_code=403)
    if not settings.auth_enabled:
        return await call_next(request)
    path = request.url.path
    public = path == "/api/health" or path.startswith("/api/auth/") or path == "/" or path.startswith("/static/")
    if public:
        return await call_next(request)
    if path.startswith("/api/") and not verify_session(request.cookies.get("drive2_session")):
        return JSONResponse({"detail": "Autenticação necessária."}, status_code=401)
    return await call_next(request)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_ROOT / "index.html")
