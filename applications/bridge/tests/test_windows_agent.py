from __future__ import annotations

import asyncio
import ctypes
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "windows-agent" / "agent.py"
SPEC = importlib.util.spec_from_file_location("bridge_windows_agent", MODULE_PATH)
assert SPEC and SPEC.loader
agent = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = agent
SPEC.loader.exec_module(agent)


def test_network_type_uses_addresses_and_tailscale_ranges() -> None:
    with patch.object(agent.socket, "gethostbyname_ex", return_value=("bridge.local", ["alias"], ["192.168.1.20"])):
        assert agent.network_type("http://bridge.local:8876") == "lan"
    with patch.object(agent.socket, "gethostbyname_ex", return_value=("bridge", [], ["100.100.10.20"])):
        assert agent.network_type("http://bridge:8876") == "tailscale"
    assert agent.network_type("https://bridge.example.ts.net") == "tailscale"


def test_screen_start_requires_local_permission() -> None:
    config = agent.AgentConfig(server_public_key="unused")
    command = {"id": "screen-command", "action": "screen_start", "arguments": {}, "signature": "unused"}
    with patch.object(agent, "verify_command", return_value=True), patch.object(agent, "notify") as notification:
        denied = asyncio.run(agent.execute_command(config, command))
        assert denied["status"] == "denied"

        config.permissions["screen_share"] = True
        consent = asyncio.run(agent.execute_command(config, command))
        assert consent["status"] == "needs_local_consent"
        assert notification.call_args.args[2] == "http://127.0.0.1:8876/?screen_request=screen-command"


def test_control_input_requires_permission_and_valid_signature() -> None:
    config = agent.AgentConfig(server_public_key="unused")
    command = {
        "id": "control-command", "action": "control_input", "signature": "unused",
        "arguments": {"event": {"type": "move", "x": 0.2, "y": 0.8, "button": "left"}},
    }
    with patch.object(agent, "verify_command", return_value=True), patch.object(agent, "execute_control_event") as execute:
        asyncio.run(agent.execute_control_input(config, command))
        execute.assert_not_called()

        config.permissions["remote_control"] = True
        asyncio.run(agent.execute_control_input(config, command))
        execute.assert_called_once_with(command["arguments"]["event"])

    with patch.object(agent, "verify_command", return_value=False), patch.object(agent, "execute_control_event") as execute:
        asyncio.run(agent.execute_control_input(config, command))
        execute.assert_not_called()


def test_unicode_text_uses_complete_windows_input_layout() -> None:
    expected_size = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert ctypes.sizeof(agent._INPUT) == expected_size

    class FakeSendInput:
        argtypes = None
        restype = None

        def __init__(self) -> None:
            self.calls: list[tuple[int, int, int, int]] = []

        def __call__(self, count, inputs, size):
            self.calls.append((count, inputs[0].ki.wScan, inputs[1].ki.dwFlags, size))
            return count

    fake = type("FakeUser32", (), {})()
    fake.SendInput = FakeSendInput()
    agent.send_unicode_text(fake, "á")

    assert fake.SendInput.calls == [(2, ord("á"), 0x0004 | 0x0002, expected_size)]
