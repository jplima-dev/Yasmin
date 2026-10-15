from __future__ import annotations

import argparse
import asyncio
import base64
import ctypes
import ipaddress
import json
import os
import socket
import subprocess
import sys
import time
import webbrowser
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx
import websockets
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


APP_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / "Bridge"
CONFIG_PATH = APP_DIR / "agent.json"
IDENTITY_PATH = APP_DIR / "identity.pem"


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long), ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class _INPUTVALUE(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("type", ctypes.c_ulong), ("value", _INPUTVALUE)]


@dataclass
class AgentConfig:
    server: str = "http://127.0.0.1:8876"
    name: str = field(default_factory=socket.gethostname)
    device_id: str | None = None
    server_public_key: str | None = None
    auth_token: str | None = None
    clipboard_enabled: bool = False
    permissions: dict[str, bool] = field(default_factory=lambda: {
        "remote_ring": True, "remote_lock": False, "screen_share": False,
        "remote_control": False, "remote_actions": False, "photos": False, "clipboard": False,
    })

    @classmethod
    def load(cls) -> "AgentConfig":
        APP_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_PATH.exists():
            return cls(**json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        return cls()

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def load_identity() -> Ed25519PrivateKey:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if IDENTITY_PATH.exists():
        key = serialization.load_pem_private_key(IDENTITY_PATH.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise RuntimeError("Identidade inválida")
        return key
    key = Ed25519PrivateKey.generate()
    IDENTITY_PATH.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ))
    return key


def public_key_text(key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.urlsafe_b64encode(raw).decode()


def websocket_url(server: str, device_id: str) -> str:
    return server.replace("https://", "wss://").replace("http://", "ws://").rstrip("/") + f"/ws/{device_id}"


def auth_headers(config: AgentConfig) -> dict[str, str]:
    if not config.auth_token:
        raise RuntimeError("O agente precisa ser pareado novamente para obter autenticação")
    return {"Authorization": f"Bearer {config.auth_token}"}


def notify(title: str, message: str, launch: str | None = None) -> None:
    try:
        from winotify import Notification
        notification = Notification(app_id="Bridge", title=title, msg=message, launch=launch or "")
        if launch:
            notification.add_actions(label="Abrir Bridge", launch=launch)
        notification.show()
    except Exception:
        print(f"[{title}] {message}")


def verify_command(command: dict[str, Any], server_public_key: str | None) -> bool:
    if not server_public_key or not command.get("signature"):
        return False
    signature = base64.urlsafe_b64decode(command["signature"])
    unsigned = {key: value for key, value in command.items() if key != "signature"}
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    public = Ed25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(server_public_key))
    try:
        public.verify(signature, canonical)
        return True
    except Exception:
        return False


def read_clipboard_text() -> str | None:
    """Leitura pequena e event-driven pelo agente, ativada explicitamente pelo usuário."""
    if os.name != "nt":
        return None
    CF_UNICODETEXT = 13
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    if not user32.OpenClipboard(None):
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return None
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return None
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


async def pair(config: AgentConfig, key: Ed25519PrivateKey) -> None:
    async with httpx.AsyncClient(base_url=config.server, timeout=15) as client:
        identity = (await client.get("/api/system/identity")).json()
        response = await client.post("/api/pairing/request", json={
            "name": config.name, "device_type": "windows", "public_key": public_key_text(key),
            "permissions": config.permissions,
        })
        response.raise_for_status(); data = response.json()
        print(f'O computador será adicionado como "{config.name}".')
        print("Veja o código de seis dígitos na janela do Bridge Core.")
        code = input("Código de pareamento: ").strip()
        if len(code) != 6 or not code.isdigit():
            raise RuntimeError("O código precisa ter exatamente seis dígitos")
        confirmed = await client.post(f"/api/pairing/{data['device_id']}/confirm", json={"code": code})
        confirmed.raise_for_status()
        confirmation = confirmed.json()
        config.device_id = data["device_id"]
        config.server_public_key = identity["public_key"]
        config.auth_token = confirmation["auth_token"]
        config.save()
        print("Computador adicionado ao Bridge.")


async def send_clipboard(config: AgentConfig, content: str, target_id: str) -> None:
    async with httpx.AsyncClient(base_url=config.server, timeout=15) as client:
        response = await client.post("/api/messages", json={
            "kind": "clipboard", "source_id": config.device_id, "target_id": target_id,
            "content": content[:200_000], "behavior": "save",
        }, headers=auth_headers(config))
        response.raise_for_status()


async def clipboard_loop(config: AgentConfig) -> None:
    last = None
    while True:
        if config.clipboard_enabled and config.permissions.get("clipboard"):
            current = read_clipboard_text()
            if current and current != last:
                last = current
                async with httpx.AsyncClient(base_url=config.server, timeout=10) as client:
                    devices = (await client.get("/api/devices", headers=auth_headers(config))).json()
                targets = [item for item in devices if item["id"] != config.device_id and item["device_type"] in {"android", "tablet"}]
                for target in targets[:1]:
                    try:
                        await send_clipboard(config, current, target["id"])
                    except Exception as exc:
                        print(f"Clipboard não entregue: {exc}", file=sys.stderr)
        await asyncio.sleep(1.2)


async def execute_command(config: AgentConfig, command: dict[str, Any]) -> dict[str, str]:
    action = command.get("action", "")
    if not verify_command(command, config.server_public_key):
        return {"status": "denied", "detail": "assinatura inválida"}
    args = command.get("arguments", {})
    try:
        if action == "ring" and config.permissions.get("remote_ring"):
            for _ in range(4):
                ctypes.windll.kernel32.Beep(880, 280); await asyncio.sleep(.12)
        elif action == "lock" and config.permissions.get("remote_lock"):
            ctypes.windll.user32.LockWorkStation()
        elif action == "open_url" and config.permissions.get("remote_actions"):
            url = args.get("url", "")
            if not url.startswith(("http://", "https://")):
                raise ValueError("URL recusada")
            webbrowser.open(url)
        elif action == "open_folder" and config.permissions.get("remote_actions"):
            requested = Path(args.get("path", "")).resolve()
            allowed = Path.home().resolve()
            if allowed not in requested.parents and requested != allowed:
                raise PermissionError("Pasta fora do perfil do usuário")
            subprocess.Popen(["explorer.exe", str(requested)])
        elif action == "notify" and config.permissions.get("remote_actions"):
            notify("Bridge", str(args.get("message", "Notificação recebida")))
        elif action == "screen_start" and config.permissions.get("screen_share"):
            command_id = quote(str(command.get("id", "")), safe="")
            handoff_url = f"{config.server.rstrip('/')}/?screen_request={command_id}"
            notify(
                "Bridge",
                "Solicitação de tela recebida. Clique para abrir o Bridge e escolher o que compartilhar.",
                handoff_url,
            )
            return {"status": "needs_local_consent", "detail": "captura nunca inicia silenciosamente"}
        else:
            return {"status": "denied", "detail": "ação desabilitada nas permissões locais"}
        return {"status": "completed", "detail": action}
    except Exception as exc:
        return {"status": "failed", "detail": str(exc)}


def execute_control_event(event: dict[str, Any]) -> None:
    if os.name != "nt":
        raise RuntimeError("Controle remoto disponível somente no Windows")
    user32 = ctypes.windll.user32
    event_type = event.get("type")
    if event_type in {"move", "down", "up"}:
        left = user32.GetSystemMetrics(76)
        top = user32.GetSystemMetrics(77)
        width = user32.GetSystemMetrics(78) or user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(79) or user32.GetSystemMetrics(1)
        x = left + round(float(event["x"]) * max(1, width - 1))
        y = top + round(float(event["y"]) * max(1, height - 1))
        user32.SetCursorPos(x, y)
        if event_type != "move":
            flags = {
                ("down", "left"): 0x0002, ("up", "left"): 0x0004,
                ("down", "right"): 0x0008, ("up", "right"): 0x0010,
            }
            user32.mouse_event(flags[(event_type, event.get("button", "left"))], 0, 0, 0, 0)
        return
    if event_type == "scroll":
        user32.mouse_event(0x0800, 0, 0, int(event.get("delta", 0)) * 120, 0)
        return
    if event_type == "key":
        virtual_keys = {"BACKSPACE": 0x08, "TAB": 0x09, "ENTER": 0x0D, "ESCAPE": 0x1B}
        key = virtual_keys[event["key"]]
        user32.keybd_event(key, 0, 0, 0)
        user32.keybd_event(key, 0, 0x0002, 0)
        return
    if event_type == "text":
        send_unicode_text(user32, event["text"])
        return
    raise ValueError("Evento de controle não reconhecido")


def send_unicode_text(user32: Any, text: str) -> None:
    """Injeta UTF-16 com o tamanho real de INPUT (40 bytes no Windows x64)."""
    send_input = user32.SendInput
    send_input.argtypes = (ctypes.c_uint, ctypes.POINTER(_INPUT), ctypes.c_int)
    send_input.restype = ctypes.c_uint
    units = text.encode("utf-16-le")
    for index in range(0, len(units), 2):
        unit = int.from_bytes(units[index:index + 2], "little")
        inputs = (_INPUT * 2)()
        inputs[0].type = inputs[1].type = 1
        inputs[0].ki = _KEYBDINPUT(0, unit, 0x0004, 0, 0)
        inputs[1].ki = _KEYBDINPUT(0, unit, 0x0004 | 0x0002, 0, 0)
        if send_input(2, inputs, ctypes.sizeof(_INPUT)) != 2:
            raise OSError("O Windows recusou a entrada de teclado")


async def execute_control_input(config: AgentConfig, command: dict[str, Any]) -> None:
    if not config.permissions.get("remote_control") or not verify_command(command, config.server_public_key):
        return
    event = command.get("arguments", {}).get("event")
    if isinstance(event, dict):
        execute_control_event(event)


def is_tailscale_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return value.lower().endswith(".ts.net")
    return address in ipaddress.ip_network("100.64.0.0/10") or address in ipaddress.ip_network("fd7a:115c:a1e0::/48")


def network_type(server: str) -> str:
    host = urlparse(server).hostname or ""
    if is_tailscale_address(host):
        return "tailscale"
    try:
        server_addresses = socket.gethostbyname_ex(host)[2]
    except OSError:
        server_addresses = []
    return "tailscale" if any(is_tailscale_address(address) for address in server_addresses) else "lan"


async def presence_payload(config: AgentConfig) -> dict[str, Any]:
    return {"network_type": network_type(config.server), "battery": None, "activity": "Agente Windows"}


async def sync_permissions(config: AgentConfig) -> None:
    assert config.device_id
    async with httpx.AsyncClient(base_url=config.server, timeout=15) as client:
        response = await client.patch(
            f"/api/devices/{config.device_id}/permissions",
            json=config.permissions,
            headers=auth_headers(config),
        )
        response.raise_for_status()


async def run_agent(config: AgentConfig) -> None:
    assert config.device_id
    tasks = [asyncio.create_task(clipboard_loop(config))]
    try:
        while True:
            try:
                await sync_permissions(config)
                async with websockets.connect(
                    websocket_url(config.server, config.device_id),
                    ping_interval=25,
                    additional_headers=auth_headers(config),
                ) as ws:
                    notify("Bridge", "Agente conectado")
                    while True:
                        await ws.send(json.dumps({"type":"ping", "presence": await presence_payload(config)}))
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=25)
                            message = json.loads(raw)
                            if message.get("type") == "command":
                                result = await execute_command(config, message["payload"])
                                await ws.send(json.dumps({"type":"command_result", "payload": {"command_id": message["payload"]["id"], **result}}))
                            elif message.get("type") == "control_input":
                                await execute_control_input(config, message["payload"])
                            elif message.get("type") == "transfer_offer":
                                notify("Bridge", f"Arquivo oferecido: {message['payload']['file_name']}")
                            elif message.get("type") == "message":
                                notify("Bridge", f"Novo {message['payload']['kind']}")
                        except asyncio.TimeoutError:
                            continue
            except Exception as exc:
                print(f"Conexão perdida: {exc}; nova tentativa em 4s", file=sys.stderr)
                await asyncio.sleep(4)
    finally:
        for task in tasks: task.cancel()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Agente nativo do Bridge para Windows")
    parser.add_argument("--server", help="URL do Bridge Core, inclusive Tailscale")
    parser.add_argument("--pair", action="store_true", help="Parear novamente")
    parser.add_argument("--enable-clipboard", action="store_true", help="Ativar sincronização explícita do clipboard")
    parser.add_argument("--enable-screen-share", action="store_true", help="Receber pedidos de tela com aprovação local")
    parser.add_argument("--enable-remote-control", action="store_true", help="Permitir controle de mouse/teclado durante tela aprovada")
    args = parser.parse_args()
    config, key = AgentConfig.load(), load_identity()
    if args.server: config.server = args.server.rstrip("/")
    if args.enable_clipboard:
        config.clipboard_enabled = True; config.permissions["clipboard"] = True
    if args.enable_screen_share:
        config.permissions["screen_share"] = True
    if args.enable_remote_control:
        config.permissions["remote_control"] = True
    config.save()
    if args.pair or not config.device_id or not config.auth_token: await pair(config, key)
    await run_agent(config)


if __name__ == "__main__":
    asyncio.run(main())
