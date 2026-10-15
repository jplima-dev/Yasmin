from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .config import ROOT, settings
from .database import Database, utcnow
from .discovery import DiscoveryService
from .events import EventHub
from .security import ActionGate, DeviceIdentity, SENSITIVE_ACTIONS, short_pairing_code


class DeviceRegistration(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    device_type: Literal["web", "windows", "android", "tablet", "server"]
    public_key: str = Field(min_length=8, max_length=500)
    permissions: dict[str, bool] = Field(default_factory=dict)


class PairingConfirmation(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class PresenceUpdate(BaseModel):
    network_type: str = "unknown"
    battery: int | None = Field(default=None, ge=0, le=100)
    activity: str | None = Field(default=None, max_length=120)
    capabilities: dict[str, bool] | None = None


class MessageCreate(BaseModel):
    kind: Literal["text", "snippet", "link", "clipboard", "photo_offer"]
    source_id: str
    target_id: str
    content: str = Field(min_length=1, max_length=200_000)
    behavior: Literal["save", "open", "ask"] = "save"

    @field_validator("content")
    @classmethod
    def validate_link(cls, value: str, info: Any) -> str:
        if info.data.get("kind") == "link":
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"}:
                raise ValueError("Links devem usar http ou https")
        return value


class TransferOffer(BaseModel):
    source_id: str
    target_id: str
    file_name: str = Field(min_length=1, max_length=255)
    total_size: int = Field(ge=0, le=50 * 1024 * 1024 * 1024)
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")

    @field_validator("file_name")
    @classmethod
    def safe_file_name(cls, value: str) -> str:
        if Path(value).name != value or value in {".", ".."}:
            raise ValueError("Nome de arquivo inválido")
        return value


class CommandRequest(BaseModel):
    actor_id: str
    target_id: str
    action: Literal["ring", "lock", "screen_start", "screen_stop", "open_url", "notify", "open_folder", "request_photo"]
    arguments: dict[str, Any] = Field(default_factory=dict)
    confirmation_token: str | None = None


class ConfirmationRequest(BaseModel):
    actor_id: str
    target_id: str
    action: str


class ShareboxCreate(BaseModel):
    owner_id: str
    kind: Literal["text", "link", "file"]
    content: str
    expires_in_minutes: int = Field(default=60, ge=1, le=10_080)


class FileRequestCreate(BaseModel):
    requester_id: str
    target_id: str
    note: str = Field(default="", max_length=500)


class RuleCreate(BaseModel):
    owner_id: str
    name: str
    trigger: dict[str, Any]
    action: dict[str, Any]
    enabled: bool = True


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class MembershipCreate(BaseModel):
    device_id: str
    role: Literal["owner", "manager", "member", "viewer"]


class SignalCreate(BaseModel):
    source_id: str
    target_id: str
    kind: Literal["offer", "answer", "ice", "end", "decline", "handoff"]
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def validate_signal_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        session_id = value.get("session_id")
        if not isinstance(session_id, str) or not 8 <= len(session_id) <= 100:
            raise ValueError("Sinal WebRTC exige session_id válido")
        if len(json.dumps(value)) > 200_000:
            raise ValueError("Sinal WebRTC excede o limite permitido")
        return value


settings.prepare()
db = Database(settings.data_dir / "bridge.sqlite3")
identity = DeviceIdentity.load_or_create(settings.data_dir / "identity.pem")
hub = EventHub()
gate = ActionGate()
screen_handoffs: dict[str, dict[str, Any]] = {}
screen_routes: dict[str, dict[str, Any]] = {}
control_sessions: dict[str, dict[str, Any]] = {}
discovery = DiscoveryService(
    settings.discovery_port,
    lambda: {
        "name": "Bridge Core",
        "url": settings.public_url,
        "fingerprint": identity.fingerprint,
        "public_key": identity.public_key,
    },
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.initialize()
    try:
        await discovery.start()
    except OSError as exc:
        db.event("discovery_unavailable", None, None, {"error": str(exc)}, security=True)
    yield
    await discovery.stop()


app = FastAPI(title="Bridge Core", version="1.1.2", lifespan=lifespan)

AUTH_COOKIE = "bridge.auth"
PUBLIC_API_PATHS = {
    "/api/health",
    "/api/system/identity",
    "/api/pairing/request",
}


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    return token if scheme.lower() == "bearer" and token else None


@app.middleware("http")
async def authenticate_api(request: Request, call_next):
    path = request.url.path
    pairing_confirmation = path.startswith("/api/pairing/") and path.endswith("/confirm")
    if path.startswith("/api/") and path not in PUBLIC_API_PATHS and not pairing_confirmation:
        token = bearer_token(request.headers.get("Authorization")) or request.cookies.get(AUTH_COOKIE)
        device = db.authenticate(token_digest(token)) if token else None
        if not device:
            return JSONResponse({"detail": "Autenticação do aparelho ausente ou revogada"}, status_code=401)
        request.state.device = device
    return await call_next(request)


def require_device(device_id: str, paired: bool = True) -> dict[str, Any]:
    device = db.row("SELECT * FROM devices WHERE id=?", (device_id,))
    if not device or device["revoked"]:
        raise HTTPException(404, "Dispositivo inexistente ou revogado")
    if paired and device["pairing_status"] != "paired":
        raise HTTPException(403, "O dispositivo ainda não foi pareado")
    return device


def require_actor(request: Request, device_id: str) -> dict[str, Any]:
    actor = getattr(request.state, "device", None)
    if not actor or actor["id"] != device_id:
        raise HTTPException(403, "O aparelho autenticado não pode agir como outro dispositivo")
    return actor


def permission_allowed(device: dict[str, Any], permission: str) -> bool:
    permissions = json.loads(device.get("permissions") or "{}")
    return bool(permissions.get(permission, False))


def normalized_control_event(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    event_type = value.get("type")
    if event_type in {"move", "down", "up"}:
        try:
            x, y = float(value.get("x")), float(value.get("y"))
        except (TypeError, ValueError):
            return None
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            return None
        button = value.get("button", "left")
        if button not in {"left", "right"}:
            return None
        return {"type": event_type, "x": x, "y": y, "button": button}
    if event_type == "scroll":
        try:
            delta = int(value.get("delta", 0))
        except (TypeError, ValueError):
            return None
        return {"type": "scroll", "delta": max(-10, min(10, delta))}
    if event_type == "text":
        text = value.get("text")
        if not isinstance(text, str) or not text or len(text) > 500:
            return None
        return {"type": "text", "text": text}
    if event_type == "key" and value.get("key") in {"ENTER", "BACKSPACE", "TAB", "ESCAPE"}:
        return {"type": "key", "key": value["key"]}
    return None


async def notify(target_id: str, kind: str, payload: dict[str, Any]) -> int:
    event = {"type": kind, "payload": payload, "at": utcnow()}
    return await hub.emit(target_id, event)


def apply_rules(owner_id: str, event_kind: str, payload: dict[str, Any]) -> list[str]:
    applied: list[str] = []
    rows = db.rows("SELECT * FROM rules WHERE owner_id=? AND enabled=1", (owner_id,))
    for row in rows:
        trigger = json.loads(row["trigger_json"])
        if trigger.get("kind") not in {None, event_kind}:
            continue
        if any(payload.get(key) != value for key, value in trigger.items() if key != "kind"):
            continue
        action = json.loads(row["action_json"])
        db.event("rule_applied", owner_id, payload.get("target_id"), {"rule_id": row["id"], "action": action})
        applied.append(row["id"])
    return applied


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "version": app.version, "time": utcnow()}


@app.get("/api/system/identity")
def system_identity() -> dict[str, str]:
    return {"public_key": identity.public_key, "fingerprint": identity.fingerprint, "url": settings.public_url}


@app.get("/api/discovery")
def discovered_peers() -> dict[str, Any]:
    return {"port": settings.discovery_port, "peers": discovery.peers()}


@app.post("/api/pairing/request", status_code=201)
def pairing_request(registration: DeviceRegistration) -> dict[str, Any]:
    code = short_pairing_code()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    device = db.register_device(registration.model_dump(), code, expires_at)
    db.event("pairing_requested", device["id"], None, {"name": device["name"]}, security=True)
    print(
        f'Bridge: código para adicionar "{device["name"]}" ({device["id"][:8]}): {code} '
        "— válido por 10 minutos",
        flush=True,
    )
    return {
        "device_id": device["id"],
        "expires_at": expires_at,
        "expires_hint": "Digite o código mostrado na janela do Bridge Core",
    }


@app.post("/api/pairing/{device_id}/confirm")
async def confirm_pairing(device_id: str, confirmation: PairingConfirmation, request: Request) -> Response:
    token = secrets.token_urlsafe(32)
    if not db.confirm_pairing(device_id, confirmation.code, token_digest(token)):
        db.event("pairing_failed", device_id, None, {}, status="denied", security=True)
        raise HTTPException(403, "Código incorreto, expirado ou dispositivo revogado")
    db.event("pairing_confirmed", device_id, None, {}, status="accepted", security=True)
    await hub.broadcast({"type": "devices_changed", "payload": {"device_id": device_id}})
    response = JSONResponse({"paired": True, "device_id": device_id, "auth_token": token})
    response.set_cookie(
        AUTH_COOKIE,
        token,
        max_age=365 * 24 * 60 * 60,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    return response


@app.delete("/api/devices/{device_id}")
async def revoke_device(device_id: str) -> dict[str, bool]:
    require_device(device_id, paired=False)
    db.execute(
        "UPDATE devices SET revoked=1, online=0, pairing_status='revoked', auth_token_hash=NULL WHERE id=?",
        (device_id,),
    )
    db.event("device_revoked", device_id, None, {}, status="completed", security=True)
    await hub.broadcast({"type": "devices_changed", "payload": {"device_id": device_id}})
    return {"revoked": True}


@app.get("/api/devices")
def list_devices() -> list[dict[str, Any]]:
    return db.list_devices()


@app.patch("/api/devices/{device_id}/favorite")
def favorite(device_id: str, enabled: bool = True) -> dict[str, Any]:
    require_device(device_id, paired=False)
    db.execute("UPDATE devices SET favorite=? WHERE id=?", (int(enabled), device_id))
    return require_device(device_id, paired=False)


@app.patch("/api/devices/{device_id}/permissions")
async def update_permissions(device_id: str, permissions: dict[str, bool], request: Request) -> dict[str, Any]:
    require_actor(request, device_id)
    require_device(device_id)
    db.execute("UPDATE devices SET permissions=? WHERE id=?", (json.dumps(permissions), device_id))
    db.event("permissions_changed", device_id, device_id, {"permissions": permissions}, security=True)
    await hub.broadcast({"type": "devices_changed", "payload": {"device_id": device_id}})
    return {"device_id": device_id, "permissions": permissions}


@app.post("/api/devices/{device_id}/presence")
async def update_presence(device_id: str, presence: PresenceUpdate, request: Request) -> dict[str, Any]:
    require_actor(request, device_id)
    require_device(device_id)
    device = db.update_presence(device_id, presence.model_dump())
    await hub.broadcast({"type": "presence", "payload": device})
    return device or {}


@app.post("/api/messages", status_code=201)
async def create_message(message: MessageCreate, request: Request) -> dict[str, Any]:
    require_actor(request, message.source_id)
    require_device(message.source_id)
    require_device(message.target_id)
    record = {
        "id": str(uuid.uuid4()), **message.model_dump(), "status": "sent", "created_at": utcnow()
    }
    db.create_record("messages", record)
    event_id = db.event(message.kind, message.source_id, message.target_id, {
        "content": message.content, "behavior": message.behavior
    }, status="sent")
    delivered = await notify(message.target_id, "message", {**record, "event_id": event_id})
    rules = apply_rules(message.target_id, message.kind, message.model_dump())
    return {**record, "delivered_live": bool(delivered), "rules_applied": rules}


@app.get("/api/messages/{device_id}")
def messages(device_id: str, request: Request, limit: int = 100) -> list[dict[str, Any]]:
    require_actor(request, device_id)
    require_device(device_id)
    return db.rows(
        "SELECT * FROM messages WHERE source_id=? OR target_id=? ORDER BY created_at DESC LIMIT ?",
        (device_id, device_id, min(limit, 500)),
    )


@app.post("/api/sharebox", status_code=201)
async def create_sharebox(item: ShareboxCreate, request: Request) -> dict[str, Any]:
    require_actor(request, item.owner_id)
    require_device(item.owner_id)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=item.expires_in_minutes)).isoformat()
    record = {
        "id": str(uuid.uuid4()), "owner_id": item.owner_id, "kind": item.kind,
        "content": item.content, "expires_at": expires, "created_at": utcnow(),
    }
    db.create_record("sharebox", record)
    await hub.broadcast({"type": "sharebox_changed", "payload": record})
    return record


@app.get("/api/sharebox")
def list_sharebox() -> list[dict[str, Any]]:
    return db.rows("SELECT * FROM sharebox WHERE expires_at IS NULL OR expires_at>? ORDER BY created_at DESC", (utcnow(),))


@app.post("/api/file-requests", status_code=201)
async def request_file(item: FileRequestCreate, request: Request) -> dict[str, Any]:
    require_actor(request, item.requester_id)
    require_device(item.requester_id)
    require_device(item.target_id)
    record = {"id": str(uuid.uuid4()), **item.model_dump(), "status": "pending", "created_at": utcnow()}
    db.create_record("file_requests", record)
    await notify(item.target_id, "file_request", record)
    db.event("file_requested", item.requester_id, item.target_id, {"request_id": record["id"]})
    return record


@app.patch("/api/file-requests/{request_id}")
def answer_file_request(request_id: str, request: Request, status: Literal["accepted", "declined", "completed"]) -> dict[str, Any]:
    record = db.row("SELECT * FROM file_requests WHERE id=?", (request_id,))
    if not record:
        raise HTTPException(404, "Solicitação não encontrada")
    actor_id = request.state.device["id"]
    if actor_id not in {record["requester_id"], record["target_id"]}:
        raise HTTPException(403, "Este aparelho não participa da solicitação")
    db.execute("UPDATE file_requests SET status=? WHERE id=?", (status, request_id))
    record["status"] = status
    return record


@app.post("/api/transfers", status_code=201)
async def offer_transfer(offer: TransferOffer, request: Request) -> dict[str, Any]:
    require_actor(request, offer.source_id)
    require_device(offer.source_id)
    require_device(offer.target_id)
    temp_path = settings.data_dir / "chunks" / f"{uuid.uuid4()}.part"
    temp_path.touch()
    transfer = db.create_transfer(offer.model_dump(), str(temp_path))
    db.event("transfer_offered", offer.source_id, offer.target_id, {"transfer_id": transfer["id"], "file_name": offer.file_name})
    await notify(offer.target_id, "transfer_offer", transfer)
    if offer.total_size == 0:
        transfer = await finalize_transfer(transfer)
    return transfer


@app.put("/api/transfers/{transfer_id}/chunks")
async def upload_chunk(transfer_id: str, request: Request, x_offset: int = Header(alias="X-Offset")) -> dict[str, Any]:
    transfer = db.transfer(transfer_id)
    if not transfer:
        raise HTTPException(404, "Transferência não encontrada")
    require_actor(request, transfer["source_id"])
    if transfer["status"] in {"paused", "cancelled", "completed"}:
        raise HTTPException(409, f"Transferência está {transfer['status']}")
    if x_offset != transfer["received_size"]:
        raise HTTPException(409, detail={"expected_offset": transfer["received_size"]})
    chunk = await request.body()
    if not chunk or len(chunk) > settings.max_chunk_bytes:
        raise HTTPException(413, f"Chunk deve ter entre 1 e {settings.max_chunk_bytes} bytes")
    # A leitura do corpo cede o event loop. Uma pausa pode ter sido aceita enquanto
    # o chunk estava em trânsito; releia o estado antes de gravar para não apagar
    # essa decisão com um status "receiving" atrasado.
    transfer = db.transfer(transfer_id)
    if not transfer:
        raise HTTPException(404, "Transferência não encontrada")
    if transfer["status"] in {"paused", "cancelled", "completed"}:
        raise HTTPException(409, f"Transferência está {transfer['status']}")
    if x_offset != transfer["received_size"]:
        raise HTTPException(409, detail={"expected_offset": transfer["received_size"]})
    if x_offset + len(chunk) > transfer["total_size"]:
        raise HTTPException(400, "Chunk excede o tamanho informado")
    with Path(transfer["temp_path"]).open("ab") as stream:
        stream.write(chunk)
    received = x_offset + len(chunk)
    status = "receiving" if received < transfer["total_size"] else "verifying"
    transfer = db.update_transfer(transfer_id, received_size=received, status=status) or transfer
    await notify(transfer["target_id"], "transfer_progress", transfer)
    if received == transfer["total_size"]:
        transfer = await finalize_transfer(transfer)
    return transfer


async def finalize_transfer(transfer: dict[str, Any]) -> dict[str, Any]:
    temporary = Path(transfer["temp_path"])
    digest = hashlib.sha256()
    with temporary.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    actual = digest.hexdigest()
    if transfer["sha256_expected"] and actual.lower() != transfer["sha256_expected"].lower():
        failed = db.update_transfer(transfer["id"], sha256_actual=actual, status="integrity_failed") or transfer
        db.event("integrity_failed", transfer["source_id"], transfer["target_id"], {"transfer_id": transfer["id"]}, security=True)
        return failed
    destination_dir = settings.received_dir / transfer["target_id"]
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / transfer["file_name"]
    if destination.exists():
        destination = destination.with_name(f"{destination.stem}-{transfer['id'][:8]}{destination.suffix}")
    temporary.replace(destination)
    completed = db.update_transfer(
        transfer["id"], sha256_actual=actual, status="completed", final_path=str(destination)
    ) or transfer
    db.event("transfer_completed", transfer["source_id"], transfer["target_id"], {
        "transfer_id": transfer["id"], "file_name": transfer["file_name"], "sha256": actual, "path": str(destination)
    }, status="completed")
    await notify(transfer["target_id"], "transfer_completed", completed)
    apply_rules(transfer["target_id"], "transfer_completed", completed)
    return completed


@app.post("/api/transfers/{transfer_id}/{action}")
async def transfer_action(transfer_id: str, action: Literal["accept", "pause", "resume", "cancel"], request: Request) -> dict[str, Any]:
    transfer = db.transfer(transfer_id)
    if not transfer:
        raise HTTPException(404, "Transferência não encontrada")
    if request.state.device["id"] not in {transfer["source_id"], transfer["target_id"]}:
        raise HTTPException(403, "Este aparelho não participa da transferência")
    transitions = {
        "accept": ({"offered"}, "accepted"), "pause": ({"accepted", "receiving"}, "paused"),
        "resume": ({"paused"}, "receiving"), "cancel": ({"offered", "accepted", "receiving", "paused"}, "cancelled"),
    }
    valid, next_status = transitions[action]
    if transfer["status"] not in valid:
        raise HTTPException(409, f"Não é possível {action} a partir de {transfer['status']}")
    transfer = db.update_transfer(transfer_id, status=next_status) or transfer
    db.event(f"transfer_{action}", transfer["source_id"], transfer["target_id"], {"transfer_id": transfer_id})
    await notify(transfer["source_id"], "transfer_status", transfer)
    return transfer


@app.get("/api/transfers")
def list_transfers(request: Request, device_id: str | None = None) -> list[dict[str, Any]]:
    actor_id = request.state.device["id"]
    if device_id and device_id != actor_id:
        raise HTTPException(403, "Só é possível consultar as próprias transferências")
    return db.rows(
        "SELECT * FROM transfers WHERE source_id=? OR target_id=? ORDER BY created_at DESC LIMIT 200",
        (actor_id, actor_id),
    )


@app.get("/api/transfers/{transfer_id}/download")
def download_transfer(transfer_id: str, request: Request) -> FileResponse:
    transfer = db.transfer(transfer_id)
    if not transfer or transfer["status"] != "completed" or not transfer["final_path"]:
        raise HTTPException(404, "Arquivo concluído não encontrado")
    if request.state.device["id"] not in {transfer["source_id"], transfer["target_id"]}:
        raise HTTPException(403, "Este aparelho não participa da transferência")
    return FileResponse(transfer["final_path"], filename=transfer["file_name"])


@app.post("/api/rules", status_code=201)
def create_rule(rule: RuleCreate, request: Request) -> dict[str, Any]:
    require_actor(request, rule.owner_id)
    require_device(rule.owner_id)
    record = {
        "id": str(uuid.uuid4()), "owner_id": rule.owner_id, "name": rule.name,
        "trigger_json": json.dumps(rule.trigger), "action_json": json.dumps(rule.action), "enabled": int(rule.enabled),
    }
    db.create_record("rules", record)
    return {**record, "trigger": rule.trigger, "action": rule.action}


@app.get("/api/rules/{owner_id}")
def list_rules(owner_id: str, request: Request) -> list[dict[str, Any]]:
    require_actor(request, owner_id)
    require_device(owner_id)
    return db.rows("SELECT * FROM rules WHERE owner_id=?", (owner_id,))


@app.post("/api/commands/confirm")
def request_confirmation(item: ConfirmationRequest, request: Request) -> dict[str, Any]:
    require_actor(request, item.actor_id)
    require_device(item.actor_id)
    require_device(item.target_id)
    if item.action not in SENSITIVE_ACTIONS:
        raise HTTPException(400, "Esta ação não exige confirmação forte")
    confirmation = gate.request(item.actor_id, item.action, item.target_id)
    db.event("sensitive_action_challenge", item.actor_id, item.target_id, {"action": item.action}, security=True)
    return {"confirmation_token": confirmation.token, "expires_at": confirmation.expires_at}


@app.post("/api/commands")
async def command(item: CommandRequest, request: Request) -> dict[str, Any]:
    require_actor(request, item.actor_id)
    require_device(item.actor_id)
    target = require_device(item.target_id)
    if item.action == "open_url":
        raw_url = item.arguments.get("url")
        if not isinstance(raw_url, str) or not raw_url or len(raw_url) > 2_048 or any(char.isspace() for char in raw_url):
            raise HTTPException(400, "URL inválida ou longa demais")
        parsed_url = urlparse(raw_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
            raise HTTPException(400, "Use uma URL completa iniciada por http:// ou https://")
        if parsed_url.username or parsed_url.password:
            raise HTTPException(400, "URLs com usuário ou senha embutidos não são permitidas")
    if item.action == "screen_start":
        session_id = item.arguments.get("session_id")
        viewer_id = item.arguments.get("viewer_id")
        if not isinstance(session_id, str) or not 8 <= len(session_id) <= 100 or viewer_id != item.actor_id:
            raise HTTPException(400, "Solicitação de tela sem sessão ou visualizador válido")
    permission = {
        "ring": "remote_ring", "lock": "remote_lock", "screen_start": "screen_share",
        "screen_stop": "screen_share", "open_url": "remote_actions", "notify": "remote_actions",
        "open_folder": "remote_actions", "request_photo": "photos",
    }[item.action]
    if not permission_allowed(target, permission):
        db.event("command_denied", item.actor_id, item.target_id, {"action": item.action, "reason": "permission"}, "denied", True)
        raise HTTPException(403, f"Permissão {permission} não foi concedida no aparelho de destino")
    if item.action in SENSITIVE_ACTIONS and not (
        item.confirmation_token and gate.consume(item.confirmation_token, item.actor_id, item.action, item.target_id)
    ):
        raise HTTPException(428, "A ação exige um token de confirmação de uso único")
    payload = {"id": str(uuid.uuid4()), **item.model_dump(exclude={"confirmation_token"}), "issued_at": utcnow()}
    if item.action == "screen_start" and target["device_type"] == "windows" and permission_allowed(target, "remote_control"):
        payload["arguments"] = {**payload["arguments"], "control_target_id": item.target_id}
    payload["signature"] = identity.sign(payload)
    if item.action == "screen_start" and target["device_type"] == "windows":
        now = time.monotonic()
        for expired_id in [
            handoff_id for handoff_id, value in screen_handoffs.items()
            if value["expires_at"] < now
        ]:
            screen_handoffs.pop(expired_id, None)
        screen_handoffs[payload["id"]] = {
            "command": payload,
            "expires_at": now + 300,
            "claimed_by": None,
        }
    delivered = await notify(item.target_id, "command", payload)
    db.event("command_issued", item.actor_id, item.target_id, {"command_id": payload["id"], "action": item.action}, "sent", True)
    return {"command_id": payload["id"], "delivered_live": bool(delivered), "signature": payload["signature"]}


@app.post("/api/screen-handoffs/{command_id}/claim")
async def claim_screen_handoff(command_id: str, request: Request) -> dict[str, Any]:
    claimant = request.state.device
    if claimant["device_type"] != "web":
        raise HTTPException(400, "Somente um painel web pode assumir a captura de tela")
    if not permission_allowed(claimant, "screen_share"):
        raise HTTPException(403, "Pedidos de tela estão desativados neste navegador")
    handoff = screen_handoffs.get(command_id)
    if not handoff or handoff["expires_at"] < time.monotonic():
        screen_handoffs.pop(command_id, None)
        raise HTTPException(410, "A solicitação de tela expirou. Envie outra pelo aparelho remoto")
    if handoff["claimed_by"] and handoff["claimed_by"] != claimant["id"]:
        raise HTTPException(409, "Esta solicitação já foi aberta em outro navegador")

    handoff["claimed_by"] = claimant["id"]
    original = handoff["command"]
    claimed_command = {
        **{key: value for key, value in original.items() if key != "signature"},
        "target_id": claimant["id"],
    }
    claimed_command["signature"] = identity.sign(claimed_command)
    session_id = original["arguments"]["session_id"]
    screen_routes[session_id] = {
        "viewer_id": original["actor_id"],
        "sharer_id": claimant["id"],
        "control_target_id": original["arguments"].get("control_target_id"),
        "expires_at": time.monotonic() + 60 * 60,
    }
    await notify(original["actor_id"], "webrtc_signal", {
        "source_id": claimant["id"],
        "target_id": original["actor_id"],
        "kind": "handoff",
        "payload": {
            "session_id": session_id,
            "previous_target_id": original["target_id"],
        },
    })
    db.event(
        "screen_handoff_claimed", claimant["id"], original["actor_id"],
        {"command_id": command_id, "session_id": session_id},
        status="accepted", security=True,
    )
    screen_handoffs.pop(command_id, None)
    return {"command": claimed_command}


@app.post("/api/control-sessions/{session_id}/approve")
async def approve_control_session(session_id: str, request: Request) -> dict[str, Any]:
    sharer = request.state.device
    route = screen_routes.get(session_id)
    if not route or route["expires_at"] < time.monotonic():
        screen_routes.pop(session_id, None)
        raise HTTPException(410, "A sessão de tela expirou")
    if route["sharer_id"] != sharer["id"]:
        raise HTTPException(403, "Somente o aparelho que compartilha a tela pode liberar o controle")
    target_id = route.get("control_target_id")
    if not target_id:
        raise HTTPException(400, "Esta transmissão não possui agente de controle")
    target = require_device(target_id)
    if target["device_type"] != "windows" or not permission_allowed(target, "remote_control"):
        raise HTTPException(403, "O controle remoto não foi permitido no agente Windows")
    token = secrets.token_urlsafe(32)
    control_sessions[session_id] = {
        **route,
        "token": token,
        "last_event_at": 0.0,
        "expires_at": time.monotonic() + 60 * 60,
    }
    await notify(route["viewer_id"], "control_status", {
        "session_id": session_id,
        "enabled": True,
        "token": token,
        "target_id": target_id,
    })
    db.event(
        "remote_control_started", sharer["id"], route["viewer_id"],
        {"session_id": session_id, "target_id": target_id}, status="accepted", security=True,
    )
    return {"session_id": session_id, "enabled": True}


@app.post("/api/signals")
async def signaling(signal: SignalCreate, request: Request) -> dict[str, Any]:
    require_actor(request, signal.source_id)
    require_device(signal.source_id)
    require_device(signal.target_id)
    delivered = await notify(signal.target_id, "webrtc_signal", signal.model_dump())
    if signal.kind in {"end", "decline"}:
        control = control_sessions.pop(signal.payload["session_id"], None)
        screen_routes.pop(signal.payload["session_id"], None)
        if control:
            db.event(
                "remote_control_ended", signal.source_id, control["viewer_id"],
                {"session_id": signal.payload["session_id"]}, status="completed", security=True,
            )
    if signal.kind != "ice":
        db.event("p2p_signal", signal.source_id, signal.target_id, {"kind": signal.kind})
    return {"relayed": bool(delivered)}


@app.post("/api/events/{event_id}/action")
async def notification_action(event_id: str, action: Literal["accept", "decline", "view", "download", "always_download"], request: Request) -> dict[str, Any]:
    event = db.row("SELECT * FROM events WHERE id=?", (event_id,))
    if not event:
        raise HTTPException(404, "Evento não encontrado")
    if request.state.device["id"] not in {event["source_id"], event["target_id"]}:
        raise HTTPException(403, "Este aparelho não participa do evento")
    db.execute("UPDATE events SET status=? WHERE id=?", (action, event_id))
    db.event("notification_action", event["target_id"], event["source_id"], {"event_id": event_id, "action": action})
    return {"event_id": event_id, "action": action}


@app.get("/api/history")
def history(limit: int = 100, security_only: bool = False) -> list[dict[str, Any]]:
    return db.history(min(limit, 500), security_only)


@app.delete("/api/history/{event_id}", status_code=204, response_class=Response)
def delete_history_item(event_id: str) -> Response:
    db.execute("DELETE FROM events WHERE id=? AND security=0", (event_id,))
    return Response(status_code=204)


@app.post("/api/teams", status_code=201)
def create_team(team: TeamCreate) -> dict[str, Any]:
    record = {"id": str(uuid.uuid4()), "name": team.name, "created_at": utcnow()}
    db.create_record("teams", record)
    return record


@app.post("/api/teams/{team_id}/members")
def add_team_member(team_id: str, member: MembershipCreate) -> dict[str, Any]:
    require_device(member.device_id)
    if not db.row("SELECT * FROM teams WHERE id=?", (team_id,)):
        raise HTTPException(404, "Equipe não encontrada")
    db.execute("INSERT OR REPLACE INTO memberships(team_id,device_id,role) VALUES(?,?,?)", (team_id, member.device_id, member.role))
    db.execute("UPDATE devices SET team_id=? WHERE id=?", (team_id, member.device_id))
    db.event("team_member_changed", None, member.device_id, {"team_id": team_id, "role": member.role}, security=True)
    return {"team_id": team_id, **member.model_dump()}


@app.get("/api/teams")
def list_teams() -> list[dict[str, Any]]:
    teams = db.rows("SELECT * FROM teams ORDER BY name")
    for team in teams:
        team["members"] = db.rows("SELECT * FROM memberships WHERE team_id=?", (team["id"],))
    return teams


@app.post("/api/drive2/archive/{transfer_id}")
def archive_to_drive2(transfer_id: str, request: Request) -> dict[str, Any]:
    transfer = db.transfer(transfer_id)
    if not transfer or transfer["status"] != "completed" or not transfer["final_path"]:
        raise HTTPException(409, "Somente transferências concluídas podem ser arquivadas")
    if request.state.device["id"] not in {transfer["source_id"], transfer["target_id"]}:
        raise HTTPException(403, "Este aparelho não participa da transferência")
    outbox = settings.data_dir / "drive2-outbox" / transfer_id
    outbox.mkdir(parents=True, exist_ok=True)
    source = Path(transfer["final_path"])
    destination = outbox / source.name
    shutil.copy2(source, destination)
    manifest = {"transfer_id": transfer_id, "file": destination.name, "sha256": transfer["sha256_actual"], "created_at": utcnow()}
    (outbox / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    db.event("drive2_queued", transfer["source_id"], transfer["target_id"], manifest)
    return {"queued": True, "outbox": str(outbox), "manifest": manifest}


@app.websocket("/ws/{device_id}")
async def websocket(device_id: str, websocket: WebSocket) -> None:
    token = bearer_token(websocket.headers.get("Authorization")) or websocket.cookies.get(AUTH_COOKIE)
    authenticated = db.authenticate(token_digest(token)) if token else None
    if not authenticated or authenticated["id"] != device_id:
        await websocket.close(code=4403)
        return
    await hub.connect(device_id, websocket)
    db.update_presence(device_id, {"network_type": "websocket"})
    await hub.broadcast({"type": "presence", "payload": {"device_id": device_id, "online": True}})
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                db.update_presence(device_id, message.get("presence", {}))
                await websocket.send_json({"type": "pong", "at": utcnow()})
            elif message.get("type") == "command_result":
                db.event("command_result", device_id, None, message.get("payload", {}), security=True)
            elif message.get("type") == "control_input":
                payload = message.get("payload", {})
                session_id = payload.get("session_id")
                control = control_sessions.get(session_id)
                if not control or control["viewer_id"] != device_id or control["expires_at"] < time.monotonic():
                    continue
                if not secrets.compare_digest(str(payload.get("token", "")), control["token"]):
                    continue
                event = normalized_control_event(payload.get("event"))
                if not event:
                    continue
                now = time.monotonic()
                if event["type"] == "move" and now - control["last_event_at"] < 0.025:
                    continue
                control["last_event_at"] = now
                command_payload = {
                    "id": str(uuid.uuid4()), "actor_id": device_id,
                    "target_id": control["control_target_id"], "action": "control_input",
                    "arguments": {"session_id": session_id, "event": event}, "issued_at": utcnow(),
                }
                command_payload["signature"] = identity.sign(command_payload)
                await notify(control["control_target_id"], "control_input", command_payload)
    except WebSocketDisconnect:
        await hub.disconnect(device_id, websocket)
        db.execute("UPDATE devices SET online=0, last_seen=? WHERE id=?", (utcnow(), device_id))
        await hub.broadcast({"type": "presence", "payload": {"device_id": device_id, "online": False}})


WEB_DIR = ROOT / "web-panel"
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
