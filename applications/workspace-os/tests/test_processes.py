from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from workspace_os.processes import ProcessManager
from workspace_os.registry import ModuleRegistry


class ProcessManagerTests(unittest.TestCase):
    def test_local_driver_environment_is_restricted_to_loopback(self) -> None:
        environment = ProcessManager._module_environment("drive2", {
            "run_local": True,
            "host": "0.0.0.0",
            "port": 8123,
            "storage_root": "data/files",
            "auth_cookie_secure": True,
            "r2_enabled": False,
        })
        self.assertEqual(environment["DRIVE2_HOST"], "127.0.0.1")
        self.assertEqual(environment["DRIVE2_PORT"], "8123")
        self.assertEqual(environment["DRIVE2_STORAGE_ROOT"], "data/files")
        self.assertEqual(environment["DRIVE2_AUTH_COOKIE_SECURE"], "false")
        self.assertEqual(environment["R2_ENABLED"], "False")

    def test_driver_command_uses_its_own_virtual_environment(self) -> None:
        workspace = Path(__file__).resolve().parents[1]
        registry = ModuleRegistry(workspace / "config/modules.json", workspace.parent)
        with tempfile.TemporaryDirectory() as temporary:
            manager = ProcessManager(registry, Path(temporary), workspace)
            command = manager._expand_command(registry.get("drive2"))
        self.assertEqual(Path(command[0]).resolve(), (workspace.parent / "driver/.venv/Scripts/python.exe").resolve())
        self.assertEqual(command[1], "run.py")

    def test_finished_service_releases_process_and_log_handles(self) -> None:
        class FakeProcess:
            pid = 4321

            def __init__(self, *args, **kwargs) -> None:
                self.returncode = None

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                self.returncode = 0
                return 0

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "service"
            project.mkdir()
            module = SimpleNamespace(
                id="service", name="Serviço", health_url=None, url=None,
                command=(str(project / "service.exe"),), installed=True, project_path=project,
            )
            registry = SimpleNamespace(get=lambda module_id: module, ecosystem_root=Path(temporary))
            manager = ProcessManager(registry, Path(temporary) / "data", Path(temporary))
            with patch("workspace_os.processes.subprocess.Popen", FakeProcess):
                manager.start("service")
                deadline = time.monotonic() + 2
                while manager._processes and time.monotonic() < deadline:
                    time.sleep(0.01)
            self.assertFalse(manager._processes)
            self.assertFalse(manager._logs)

    def test_managed_service_receives_the_central_core_origin(self) -> None:
        captured: dict[str, object] = {}

        class FakeProcess:
            pid = 9876
            returncode = None

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                self.returncode = 0
                return 0

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "service"
            project.mkdir()
            module = SimpleNamespace(
                id="service", name="Serviço", health_url=None, url=None,
                command=(str(project / "service.exe"),), installed=True, project_path=project,
            )
            registry = SimpleNamespace(
                get=lambda module_id: module, ecosystem_root=Path(temporary),
                core_origin=SimpleNamespace(url="http://127.0.0.1:8790"),
            )
            manager = ProcessManager(registry, Path(temporary) / "data", Path(temporary), logs=Mock())
            with patch("workspace_os.processes.subprocess.Popen", side_effect=lambda *args, **kwargs: (captured.update(kwargs) or FakeProcess())):
                manager.start("service")
            deadline = time.monotonic() + 2
            while (manager._processes or manager._logs) and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(manager._processes)
            self.assertFalse(manager._logs)
            self.assertEqual(captured["env"]["WORKSPACE_CORE_ORIGIN"], "http://127.0.0.1:8790")

    def test_command_expansion_preserves_non_placeholder_braces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            module = SimpleNamespace(
                project_path=project,
                command=("tool.exe", "--expression", "if ($x) { Write-Output $x }", "{project}"),
            )
            registry = SimpleNamespace(ecosystem_root=project)
            manager = ProcessManager(registry, project / "data", project)
            command = manager._expand_command(module)
        self.assertEqual(command[2], "if ($x) { Write-Output $x }")
        self.assertEqual(command[3], str(project))


if __name__ == "__main__":
    unittest.main()
