from __future__ import annotations

import asyncio
import hashlib
import tempfile
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient

import core.main as bridge
from core.database import Database


def register(
    client: TestClient, name: str, permissions: dict | None = None, device_type: str = "web",
) -> dict[str, str]:
    pending = client.post("/api/pairing/request", json={
        "name": name, "device_type": device_type, "public_key": f"public-{name}-abcdefgh",
        "permissions": permissions or {},
    }).json()
    assert "code" not in pending
    stored = bridge.db.row("SELECT pairing_code FROM devices WHERE id=?", (pending["device_id"],))
    response = client.post(f"/api/pairing/{pending['device_id']}/confirm", json={"code": stored["pairing_code"]})
    assert response.status_code == 200
    return {"id": pending["device_id"], "token": response.json()["auth_token"]}


def auth(device: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {device['token']}"}


def test_pair_message_sharebox_and_sensitive_command() -> None:
    with tempfile.TemporaryDirectory() as directory:
        bridge.db = Database(Path(directory) / "bridge.sqlite3")
        with TestClient(bridge.app) as client:
            source = register(client, "source")
            target = register(client, "target", {"remote_lock": True})
            presence = client.post(f"/api/devices/{source['id']}/presence", json={"network_type":"lan","battery":88,"activity":"test"}, headers=auth(source))
            assert presence.status_code == 200

            message = client.post("/api/messages", json={
                "kind":"snippet", "source_id":source["id"], "target_id":target["id"],
                "content":"print('bridge')", "behavior":"save",
            }, headers=auth(source))
            assert message.status_code == 201
            assert client.get(f"/api/messages/{target['id']}", headers=auth(target)).json()[0]["kind"] == "snippet"

            box = client.post("/api/sharebox", json={
                "owner_id":source["id"],"kind":"text","content":"temporário","expires_in_minutes":10,
            }, headers=auth(source))
            assert box.status_code == 201
            assert len(client.get("/api/sharebox", headers=auth(source)).json()) == 1

            denied = client.post("/api/commands", json={
                "actor_id":source["id"],"target_id":target["id"],"action":"lock","arguments":{},
            }, headers=auth(source))
            assert denied.status_code == 428
            token = client.post("/api/commands/confirm", json={
                "actor_id":source["id"],"target_id":target["id"],"action":"lock",
            }, headers=auth(source)).json()["confirmation_token"]
            command = client.post("/api/commands", json={
                "actor_id":source["id"],"target_id":target["id"],"action":"lock","arguments":{},"confirmation_token":token,
            }, headers=auth(source))
            assert command.status_code == 200
            assert command.json()["signature"]

            impersonation = client.post("/api/messages", json={
                "kind":"text", "source_id":source["id"], "target_id":target["id"],
                "content":"forged", "behavior":"save",
            }, headers=auth(target))
            assert impersonation.status_code == 403


def test_screen_permission_is_self_managed_and_signals_are_authenticated() -> None:
    with tempfile.TemporaryDirectory() as directory:
        bridge.db = Database(Path(directory) / "bridge.sqlite3")
        with TestClient(bridge.app) as client:
            viewer = register(client, "screen-viewer")
            sharer = register(client, "screen-sharer")
            permissions = {
                "remote_ring": True, "remote_lock": False, "screen_share": True,
                "remote_actions": True, "photos": True, "clipboard": True,
            }

            forged = client.patch(
                f"/api/devices/{sharer['id']}/permissions", json=permissions, headers=auth(viewer),
            )
            assert forged.status_code == 403
            updated = client.patch(
                f"/api/devices/{sharer['id']}/permissions", json=permissions, headers=auth(sharer),
            )
            assert updated.status_code == 200
            assert updated.json()["permissions"]["screen_share"] is True

            confirmation = client.post("/api/commands/confirm", json={
                "actor_id": viewer["id"], "target_id": sharer["id"], "action": "screen_start",
            }, headers=auth(viewer)).json()
            command = client.post("/api/commands", json={
                "actor_id": viewer["id"], "target_id": sharer["id"], "action": "screen_start",
                "arguments": {"session_id": "screen-session", "viewer_id": viewer["id"]},
                "confirmation_token": confirmation["confirmation_token"],
            }, headers=auth(viewer))
            assert command.status_code == 200

            offer = client.post("/api/signals", json={
                "source_id": sharer["id"], "target_id": viewer["id"], "kind": "offer",
                "payload": {"session_id": "screen-session", "description": {"type": "offer", "sdp": "test"}},
            }, headers=auth(sharer))
            assert offer.status_code == 200
            ended = client.post("/api/signals", json={
                "source_id": viewer["id"], "target_id": sharer["id"], "kind": "end",
                "payload": {"session_id": "screen-session", "reason": "done"},
            }, headers=auth(viewer))
            assert ended.status_code == 200
            impersonated = client.post("/api/signals", json={
                "source_id": sharer["id"], "target_id": viewer["id"], "kind": "decline",
                "payload": {"session_id": "screen-session"},
            }, headers=auth(viewer))
            assert impersonated.status_code == 403

            agent = register(client, "screen-agent", {"screen_share": True, "remote_control": True}, "windows")
            agent_confirmation = client.post("/api/commands/confirm", json={
                "actor_id": viewer["id"], "target_id": agent["id"], "action": "screen_start",
            }, headers=auth(viewer)).json()
            agent_command = client.post("/api/commands", json={
                "actor_id": viewer["id"], "target_id": agent["id"], "action": "screen_start",
                "arguments": {"session_id": "agent-screen-session", "viewer_id": viewer["id"]},
                "confirmation_token": agent_confirmation["confirmation_token"],
            }, headers=auth(viewer))
            assert agent_command.status_code == 200
            claimed = client.post(
                f"/api/screen-handoffs/{agent_command.json()['command_id']}/claim",
                headers=auth(sharer),
            )
            assert claimed.status_code == 200
            assert claimed.json()["command"]["target_id"] == sharer["id"]
            assert claimed.json()["command"]["arguments"]["session_id"] == "agent-screen-session"
            assert claimed.json()["command"]["arguments"]["control_target_id"] == agent["id"]

            forged_control = client.post(
                "/api/control-sessions/agent-screen-session/approve", headers=auth(viewer),
            )
            assert forged_control.status_code == 403
            approved_control = client.post(
                "/api/control-sessions/agent-screen-session/approve", headers=auth(sharer),
            )
            assert approved_control.status_code == 200
            assert bridge.control_sessions["agent-screen-session"]["control_target_id"] == agent["id"]
            agent_ended = client.post("/api/signals", json={
                "source_id": viewer["id"], "target_id": sharer["id"], "kind": "end",
                "payload": {"session_id": "agent-screen-session", "reason": "done"},
            }, headers=auth(viewer))
            assert agent_ended.status_code == 200
            assert "agent-screen-session" not in bridge.control_sessions

            valid_url = client.post("/api/commands", json={
                "actor_id": viewer["id"], "target_id": sharer["id"], "action": "open_url",
                "arguments": {"url": "https://example.com/path?q=bridge"},
            }, headers=auth(viewer))
            assert valid_url.status_code == 200
            for unsafe_url in (
                "javascript:alert(1)", "http://", "https://user:secret@example.com", "https://exa mple.com",
            ):
                rejected = client.post("/api/commands", json={
                    "actor_id": viewer["id"], "target_id": sharer["id"], "action": "open_url",
                    "arguments": {"url": unsafe_url},
                }, headers=auth(viewer))
                assert rejected.status_code == 400


def test_remote_control_events_are_strictly_normalized() -> None:
    assert bridge.normalized_control_event({"type": "move", "x": 0.25, "y": 0.75}) == {
        "type": "move", "x": 0.25, "y": 0.75, "button": "left",
    }
    assert bridge.normalized_control_event({"type": "scroll", "delta": 99}) == {
        "type": "scroll", "delta": 10,
    }
    assert bridge.normalized_control_event({"type": "key", "key": "ENTER"}) == {
        "type": "key", "key": "ENTER",
    }
    assert bridge.normalized_control_event({"type": "move", "x": -1, "y": 0}) is None
    assert bridge.normalized_control_event({"type": "key", "key": "DELETE"}) is None
    assert bridge.normalized_control_event({"type": "text", "text": "x" * 501}) is None


def test_chunked_transfer_pause_resume_and_integrity() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bridge.db = Database(root / "bridge.sqlite3")
        bridge.settings = replace(bridge.settings, data_dir=root / "data", received_dir=root / "received", max_chunk_bytes=16)
        bridge.settings.prepare()
        with TestClient(bridge.app) as client:
            source = register(client, "sender")
            target = register(client, "receiver")
            payload = b"bridge-transfer-ok"
            offered = client.post("/api/transfers", json={
                "source_id":source["id"], "target_id":target["id"], "file_name":"sample.txt",
                "total_size":len(payload), "sha256":hashlib.sha256(payload).hexdigest(),
            }, headers=auth(source))
            assert offered.status_code == 201
            transfer_id = offered.json()["id"]

            first = client.put(f"/api/transfers/{transfer_id}/chunks", content=payload[:8], headers={**auth(source), "X-Offset":"0","Content-Type":"application/octet-stream"})
            assert first.status_code == 200
            assert client.post(f"/api/transfers/{transfer_id}/pause", headers=auth(source)).json()["status"] == "paused"
            blocked = client.put(f"/api/transfers/{transfer_id}/chunks", content=payload[8:16], headers={**auth(source), "X-Offset":"8","Content-Type":"application/octet-stream"})
            assert blocked.status_code == 409
            assert client.post(f"/api/transfers/{transfer_id}/resume", headers=auth(source)).json()["status"] == "receiving"
            second = client.put(f"/api/transfers/{transfer_id}/chunks", content=payload[8:16], headers={**auth(source), "X-Offset":"8","Content-Type":"application/octet-stream"})
            assert second.status_code == 200
            completed = client.put(f"/api/transfers/{transfer_id}/chunks", content=payload[16:], headers={**auth(source), "X-Offset":"16","Content-Type":"application/octet-stream"})
            assert completed.status_code == 200
            assert completed.json()["status"] == "completed"
            assert completed.json()["sha256_actual"] == hashlib.sha256(payload).hexdigest()
            assert client.get(f"/api/transfers/{transfer_id}/download", headers=auth(target)).content == payload


def test_transfer_without_browser_hash_uses_server_digest() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bridge.db = Database(root / "bridge.sqlite3")
        bridge.settings = replace(bridge.settings, data_dir=root / "data", received_dir=root / "received", max_chunk_bytes=64)
        bridge.settings.prepare()
        with TestClient(bridge.app) as client:
            source = register(client, "lan-http-sender")
            target = register(client, "receiver")
            payload = b"mobile-browser-upload"
            offered = client.post("/api/transfers", json={
                "source_id": source["id"], "target_id": target["id"], "file_name": "mobile.txt",
                "total_size": len(payload), "sha256": None,
            }, headers=auth(source))
            assert offered.status_code == 201

            completed = client.put(
                f"/api/transfers/{offered.json()['id']}/chunks",
                content=payload,
                headers={**auth(source), "X-Offset": "0", "Content-Type": "application/octet-stream"},
            )
            assert completed.status_code == 200
            assert completed.json()["status"] == "completed"
            assert completed.json()["sha256_expected"] is None
            assert completed.json()["sha256_actual"] == hashlib.sha256(payload).hexdigest()


def test_pause_wins_over_chunk_already_in_transit() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        bridge.db = Database(root / "bridge.sqlite3")
        bridge.settings = replace(bridge.settings, data_dir=root / "data", received_dir=root / "received", max_chunk_bytes=16)
        bridge.settings.prepare()
        with TestClient(bridge.app) as client:
            source = register(client, "race-sender")
            target = register(client, "race-receiver")
            offered = client.post("/api/transfers", json={
                "source_id": source["id"], "target_id": target["id"], "file_name": "race.bin",
                "total_size": 8,
            }, headers=auth(source)).json()
            Path(offered["temp_path"]).write_bytes(b"1234")
            bridge.db.update_transfer(offered["id"], received_size=4, status="receiving")

            async def scenario() -> None:
                started = asyncio.Event()
                release = asyncio.Event()

                class DelayedRequest:
                    state = SimpleNamespace(device={"id": source["id"]})

                    async def body(self) -> bytes:
                        started.set()
                        await release.wait()
                        return b"5678"

                request = DelayedRequest()
                uploading = asyncio.create_task(bridge.upload_chunk(offered["id"], request, 4))
                await started.wait()
                paused = await bridge.transfer_action(offered["id"], "pause", request)
                assert paused["status"] == "paused"
                release.set()
                try:
                    await uploading
                except HTTPException as error:
                    assert error.status_code == 409
                else:
                    raise AssertionError("O chunk em trânsito deveria respeitar a pausa")

            asyncio.run(scenario())
            stored = bridge.db.transfer(offered["id"])
            assert stored["status"] == "paused"
            assert stored["received_size"] == 4
