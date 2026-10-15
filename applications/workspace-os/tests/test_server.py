from __future__ import annotations

import json
import http.client
import os
import shutil
import tempfile
import threading
import time
import unittest
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener, install_opener, urlopen

from workspace_os.activity import ActivityStore
from workspace_os.clipboard import ClipboardStore
from workspace_os.blackbox import BlackBoxStore
from workspace_os.processes import ProcessManager
from workspace_os.presets import PresetStore
from workspace_os import __version__
from workspace_os.platform import GitProjects, ModuleDataStore, PortableArchive
from workspace_os.dropzone import DropzoneStore
from workspace_os.integrations import IntegrationProfiles
from workspace_os.registry import ModuleRegistry
from workspace_os.server import AppContext, WorkspaceServer, decode_terminal_output, find_python
from workspace_os.settings import SettingsStore
from workspace_os.startup import WindowsStartup


class WorkspaceServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        workspace = Path(__file__).resolve().parents[1]
        settings = SettingsStore(Path(self.temporary.name) / "data")
        registry = ModuleRegistry(workspace / "config/modules.json", workspace.parent)
        dropzone = DropzoneStore(Path(self.temporary.name) / "data")
        activity = ActivityStore(Path(self.temporary.name) / "data")
        presets = PresetStore(Path(self.temporary.name) / "data")
        clipboard = ClipboardStore(Path(self.temporary.name) / "data")
        module_data = ModuleDataStore(Path(self.temporary.name) / "data")
        context = AppContext(
            workspace_root=workspace,
            web_root=workspace / "web",
            design_root=workspace.parent / "workspace-design-system" / "src",
            registry=registry,
            settings=settings,
            processes=ProcessManager(registry, settings.data_dir, workspace),
            startup=WindowsStartup(workspace / "launcher.py", Path(self.temporary.name) / "Startup"),
            dropzone=dropzone,
            activity=activity,
            presets=presets,
            clipboard=clipboard,
            integrations=IntegrationProfiles(Path(self.temporary.name) / "Bridge"),
            module_data=module_data,
            portable=PortableArchive(settings, activity, presets, clipboard, dropzone, module_data, workspace.parent),
            git=GitProjects(workspace.parent),
            blackbox=BlackBoxStore(Path(self.temporary.name) / "data"),
        )
        self.server = WorkspaceServer(("127.0.0.1", 0), context)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.cookie_jar = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookie_jar))
        install_opener(self.opener)
        with self.opener.open(f"{self.base}/api/session", timeout=2):
            pass

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server.context.processes.stop_all()
        self.thread.join(timeout=2)
        self.temporary.cleanup()
        install_opener(None)

    def test_health_endpoint(self) -> None:
        with urlopen(f"{self.base}/api/health", timeout=2) as response:
            payload = json.load(response)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["version"], __version__)

    def test_unknown_api_route_returns_json_404(self) -> None:
        with self.assertRaises(HTTPError) as failed:
            urlopen(f"{self.base}/api/does-not-exist", timeout=2)
        self.assertEqual(failed.exception.code, 404)
        self.assertEqual(json.loads(failed.exception.read())["error"], "Rota da API não encontrada.")

    def test_split_view_coordinator_is_served_by_the_core(self) -> None:
        with urlopen(f"{self.base}/split.html", timeout=3) as response:
            content = response.read().decode("utf-8")
            policy = response.headers.get("Content-Security-Policy", "")
        self.assertIn("/core/split-page.js", content)
        self.assertIn("frame-src 'self'", policy)

    def test_mutations_require_a_temporary_local_session(self) -> None:
        unauthenticated = build_opener()
        request = Request(
            f"{self.base}/api/settings", method="POST", data=b'{}',
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as denied:
            unauthenticated.open(request, timeout=2)
        self.assertEqual(denied.exception.code, 401)

    def test_yasmin_command_uses_existing_session_and_proxy(self) -> None:
        request = Request(
            f"{self.base}/api/yasmin/command", method="POST",
            data=json.dumps({"texto": "abra o Organizador"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as denied:
            build_opener().open(request, timeout=2)
        self.assertEqual(denied.exception.code, 401)

        chamadas = []

        def responder(handler, metodo, caminho, payload):
            chamadas.append((metodo, caminho, payload))
            handler._json({"ok": True, "resposta": "Abri Organizador."})

        with patch("workspace_os.server.WorkspaceRequestHandler._proxy_yasmin", responder):
            with self.opener.open(request, timeout=2) as response:
                self.assertEqual(json.load(response)["resposta"], "Abri Organizador.")
        self.assertEqual(chamadas, [("POST", "/command", {"texto": "abra o Organizador"})])

    def test_yasmin_proxy_transports_structured_result(self) -> None:
        class BridgeHandler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):  # noqa: N802
                content = b'{"ok":true,"status":"pronta"}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

            def do_POST(self):  # noqa: N802
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.headers.get("X-Yasmin-Bridge") != "workspace-os" or request.get("texto") != "abra o Organizador":
                    self.send_error(403)
                    return
                content = json.dumps({"ok": True, "resposta": "Abri Organizador.", "aplicacao": "organizer"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

        bridge = ThreadingHTTPServer(("127.0.0.1", 0), BridgeHandler)
        thread = threading.Thread(target=bridge.serve_forever, daemon=True)
        thread.start()
        try:
            with patch("workspace_os.server.YASMIN_BRIDGE_PORT", bridge.server_address[1]):
                with self.opener.open(f"{self.base}/api/yasmin/health", timeout=2) as response:
                    self.assertEqual(json.load(response)["status"], "pronta")
                request = Request(
                    f"{self.base}/api/yasmin/command", method="POST",
                    data=json.dumps({"texto": "abra o Organizador"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with self.opener.open(request, timeout=2) as response:
                    self.assertEqual(json.load(response)["aplicacao"], "organizer")
        finally:
            bridge.shutdown()
            bridge.server_close()
            thread.join(timeout=2)

    def test_capabilities_are_discovered_from_module_manifests(self) -> None:
        with urlopen(f"{self.base}/api/modules/capabilities", timeout=2) as response:
            modules = {item["id"]: item for item in json.load(response)["modules"]}
        self.assertTrue(modules["writer"]["capabilities"]["print"])
        self.assertTrue(modules["terminal"]["permissions"])

    def test_terminal_runs_commands_without_per_command_confirmation(self) -> None:
        request = Request(
            f"{self.base}/api/terminal/command", method="POST",
            data=json.dumps({"command": "Write-Output 'Remove-Item -Recurse -Force'"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15) as response:
            payload = json.load(response)
        self.assertEqual(payload["exitCode"], 0)
        self.assertEqual(payload["permission"], "terminal:unrestricted")
        self.assertIn("Remove-Item -Recurse -Force", payload["stdout"])

    def test_terminal_allows_external_directories_without_confirmation(self) -> None:
        request = Request(
            f"{self.base}/api/terminal/command", method="POST",
            data=json.dumps({"command": f'cd "{self.temporary.name}"'}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=4) as response:
            payload = json.load(response)
        self.assertEqual(payload["exitCode"], 0)
        self.assertEqual(Path(payload["cwd"]), Path(self.temporary.name))

        request = Request(
            f"{self.base}/api/terminal/command", method="POST",
            data=json.dumps({"command": f'Get-Item "{self.temporary.name}"'}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15) as response:
            external = json.load(response)
        self.assertEqual(external["exitCode"], 0)
        self.assertEqual(external["permission"], "terminal:unrestricted")

    @unittest.skipUnless(shutil.which("powershell.exe") or shutil.which("powershell"), "PowerShell não disponível")
    def test_terminal_async_process_reports_metrics_and_audit(self) -> None:
        request = Request(
            f"{self.base}/api/terminal/processes", method="POST",
            data=json.dumps({"command": "Write-Output terminal-async-ok", "sessionId": "test-tab"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=4) as response:
            started = json.load(response)
        self.assertEqual(started["status"], "running")
        self.assertGreater(started["pid"], 0)

        result = started
        deadline = time.monotonic() + 8
        while result["status"] == "running" and time.monotonic() < deadline:
            time.sleep(0.05)
            with urlopen(f"{self.base}/api/terminal/processes/{started['executionId']}", timeout=3) as response:
                result = json.load(response)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["exitCode"], 0)
        self.assertIn("terminal-async-ok", result["stdout"])
        self.assertIn("resources", result)
        self.assertGreaterEqual(result["durationMs"], 0)

        deadline = time.monotonic() + 2
        audit = []
        while time.monotonic() < deadline:
            with urlopen(f"{self.base}/api/terminal/audit?limit=20", timeout=3) as response:
                audit = json.load(response)["items"]
            if any(item.get("executionId") == started["executionId"] and item.get("event") == "terminal.execution.completed" for item in audit):
                break
            time.sleep(0.05)
        self.assertTrue(any(item.get("executionId") == started["executionId"] for item in audit))

    @unittest.skipUnless(shutil.which("powershell.exe") or shutil.which("powershell"), "PowerShell não disponível")
    def test_terminal_async_process_can_cancel_process_tree(self) -> None:
        request = Request(
            f"{self.base}/api/terminal/processes", method="POST",
            data=json.dumps({"command": "Start-Sleep -Seconds 20", "sessionId": "cancel-tab"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=4) as response:
            started = json.load(response)
        duplicate = Request(
            f"{self.base}/api/terminal/processes", method="POST",
            data=json.dumps({"command": "Write-Output repetido", "sessionId": "cancel-tab"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(HTTPError) as denied_duplicate:
            urlopen(duplicate, timeout=4)
        self.assertEqual(denied_duplicate.exception.code, 400)
        cancel = Request(f"{self.base}/api/terminal/processes/{started['executionId']}", method="DELETE")
        with urlopen(cancel, timeout=10) as response:
            result = json.load(response)
        deadline = time.monotonic() + 5
        while result["status"] == "running" and time.monotonic() < deadline:
            time.sleep(0.05)
            with urlopen(f"{self.base}/api/terminal/processes/{started['executionId']}", timeout=3) as response:
                result = json.load(response)
        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(result["pid"], started["pid"])

    def test_terminal_completions_return_installed_commands(self) -> None:
        with urlopen(f"{self.base}/api/terminal/completions?prefix=git", timeout=8) as response:
            items = json.load(response)["items"]
        self.assertIsInstance(items, list)
        if shutil.which("git") or shutil.which("git.exe"):
            self.assertTrue(any(item["value"].lower().startswith("git") for item in items))

    def test_terminal_completions_do_not_wait_for_command_discovery(self) -> None:
        entered = threading.Event()
        release = threading.Event()

        def slow_discovery() -> list[str]:
            entered.set()
            release.wait(2)
            return ["git"]

        manager = self.server.context.terminal_executions
        started = time.monotonic()
        try:
            with patch.object(manager, "_discover_available_commands", side_effect=slow_discovery):
                with urlopen(f"{self.base}/api/terminal/completions?prefix=git", timeout=2) as response:
                    items = json.load(response)["items"]
                self.assertTrue(entered.wait(1))
        finally:
            release.set()
        self.assertLess(time.monotonic() - started, 1.5)
        self.assertTrue(any(item["value"] == "git" for item in items))

    def test_shutdown_endpoint_stops_server(self) -> None:
        request = Request(
            f"{self.base}/api/shutdown", method="POST", data=b"{}",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=2) as response:
            self.assertTrue(json.load(response)["ok"])
        self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive())

    def test_modules_endpoint_does_not_expose_commands_or_paths(self) -> None:
        with urlopen(f"{self.base}/api/modules", timeout=3) as response:
            payload = json.load(response)
        organizer = next(item for item in payload["modules"] if item["id"] == "organizer")
        self.assertNotIn("command", organizer)
        self.assertNotIn("project_path", organizer)
        self.assertTrue(organizer["installed"])

    def test_static_module_is_served_inside_declared_project(self) -> None:
        with urlopen(f"{self.base}/module/json/index.html", timeout=3) as response:
            content = response.read().decode("utf-8")
        self.assertIn("Ink JSON", content)

    def test_web_service_workspace_shell_is_served_without_exposing_its_frontend(self) -> None:
        with urlopen(f"{self.base}/module/notebook/workspace/index.html", timeout=3) as response:
            shell = response.read().decode("utf-8")
        self.assertIn('data-module-id="notebook"', shell)
        self.assertIn('module-bootstrap.js', shell)
        with self.assertRaises(HTTPError) as denied:
            urlopen(f"{self.base}/module/notebook/frontend/index.html", timeout=3)
        self.assertEqual(denied.exception.code, 404)

    def test_remote_driver_uses_local_module_shell_and_proxies_its_api(self) -> None:
        class RemoteDriverHandler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:  # noqa: N802
                content = json.dumps({"status": "ok", "source": "tablet"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Set-Cookie", "drive2_session=test; Path=/; HttpOnly; SameSite=lax")
                self.end_headers()
                self.wfile.write(content)

        remote = ThreadingHTTPServer(("127.0.0.1", 0), RemoteDriverHandler)
        thread = threading.Thread(target=remote.serve_forever, daemon=True)
        thread.start()
        try:
            settings = self.server.context.settings.load()
            settings["module_configs"]["drive2"]["run_local"] = False
            remote_url = f"http://127.0.0.1:{remote.server_address[1]}"
            self.server.context.settings.update({
                "module_configs": settings["module_configs"],
                "module_urls": {"drive2": remote_url},
            })

            with urlopen(f"{self.base}/api/modules", timeout=3) as response:
                modules = json.load(response)["modules"]
            driver = next(item for item in modules if item["id"] == "drive2")
            self.assertEqual(driver["url"], "/module/drive2/web/index.html")
            self.assertEqual(driver["serviceUrl"], remote_url)

            with urlopen(f"{self.base}{driver['url']}", timeout=3) as response:
                shell = response.read().decode("utf-8")
            self.assertIn('data-module-id="drive2"', shell)
            self.assertIn('/module/drive2/web/css/workspace.css', shell)
            self.assertIn('module-bootstrap.js', shell)

            with urlopen(f"{self.base}/api/driver-remote/api/health", timeout=3) as response:
                payload = json.load(response)
                cookie = response.headers.get("Set-Cookie")
            self.assertEqual(payload["source"], "tablet")
            self.assertIn("drive2_session=test", cookie)

            with self.assertRaises(HTTPError) as denied:
                urlopen(f"{self.base}/module/drive2/.env", timeout=3)
            self.assertEqual(denied.exception.code, 404)
        finally:
            remote.shutdown()
            remote.server_close()
            thread.join(timeout=2)

    def test_shared_design_system_is_served(self) -> None:
        with urlopen(f"{self.base}/design-system/workspace-ui.css", timeout=3) as response:
            content = response.read().decode("utf-8")
        self.assertTrue("components.css" in content or "--ws-color-background" in content)

    def test_bridge_agent_profile_can_be_updated(self) -> None:
        payload = json.dumps({
            "server": "http://127.0.0.1:9900",
            "name": "Notebook Ink",
            "clipboard_enabled": True,
            "permissions": {"remote_ring": True, "remote_lock": False},
        }).encode("utf-8")
        request = Request(
            f"{self.base}/api/integrations/bridge-agent",
            method="POST",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=3) as response:
            result = json.load(response)
        self.assertEqual(result["name"], "Notebook Ink")
        self.assertTrue(result["clipboard_enabled"])

    def test_loopback_modules_can_read_settings_with_cors(self) -> None:
        request = Request(
            f"{self.base}/api/settings",
            headers={"Origin": "http://127.0.0.1:5173"},
        )
        with urlopen(request, timeout=3) as response:
            payload = json.load(response)
            allowed_origin = response.headers.get("Access-Control-Allow-Origin")
        self.assertEqual(payload["theme"], "light")
        self.assertEqual(allowed_origin, "http://127.0.0.1:5173")

    def test_cors_preflight_accepts_only_loopback_origin(self) -> None:
        request = Request(
            f"{self.base}/api/settings",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:4173",
                "Access-Control-Request-Method": "POST",
            },
        )
        with urlopen(request, timeout=3) as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://localhost:4173")

    def test_invalid_content_length_returns_json_error_without_stopping_server(self) -> None:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=3)
        connection.putrequest("POST", "/api/settings")
        connection.putheader("X-Workspace-Token", self.server.context.auth.token)
        connection.putheader("Content-Length", "-1")
        connection.endheaders()
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        self.assertEqual(response.status, 400)
        self.assertIn("Content-Length", payload["error"])
        with urlopen(f"{self.base}/api/health", timeout=2) as health:
            self.assertEqual(health.status, 200)

    def test_invalid_log_limit_falls_back_to_safe_default(self) -> None:
        with urlopen(f"{self.base}/api/terminal/audit?limit=not-a-number", timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertIsInstance(json.load(response)["items"], list)

    def test_unexpected_get_failure_returns_json_and_keeps_server_alive(self) -> None:
        with patch.object(self.server.context.terminal_executions, "completions", side_effect=PermissionError("bloqueado")):
            with self.assertRaises(HTTPError) as failed:
                urlopen(f"{self.base}/api/terminal/completions?prefix=git", timeout=3)
        self.assertEqual(failed.exception.code, 500)
        self.assertIn("falha interna", failed.exception.read().decode("utf-8"))
        with urlopen(f"{self.base}/api/health", timeout=2) as response:
            self.assertEqual(response.status, 200)

    def test_terminal_runs_command_and_tracks_directory(self) -> None:
        payload = json.dumps({"command": "echo terminal-ok"}).encode("utf-8")
        request = Request(
            f"{self.base}/api/terminal/command",
            method="POST",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
        self.assertTrue(result["ok"])
        self.assertIn("terminal-ok", "\n".join(result["stdout"]))
        self.assertTrue(Path(result["cwd"]).is_dir())

    def test_terminal_preserves_utf8_accents(self) -> None:
        payload = json.dumps({"command": "Write-Output 'ação, configuração e café'"}, ensure_ascii=False).encode("utf-8")
        request = Request(
            f"{self.base}/api/terminal/command", method="POST", data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
        self.assertTrue(result["ok"], "\n".join(result["stderr"]))
        self.assertIn("ação, configuração e café", "\n".join(result["stdout"]))

    @unittest.skipUnless(os.name == "nt", "Codec ANSI do Windows não está disponível")
    def test_terminal_decodes_legacy_windows_accents(self) -> None:
        message = "Não é possível inicializar o dispositivo PRN"
        self.assertEqual(decode_terminal_output(message.encode("mbcs"), "mbcs"), message)

    @unittest.skipUnless(os.name == "nt", "Comando print.exe só existe no Windows")
    def test_terminal_decodes_native_windows_command(self) -> None:
        payload = json.dumps({"command": "print /?"}).encode("utf-8")
        request = Request(
            f"{self.base}/api/terminal/command", method="POST", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
        output = "\n".join([*result["stdout"], *result["stderr"]])
        self.assertTrue(output.strip(), result)
        self.assertNotIn("�", output)

    def test_terminal_explains_python_expression_in_shell(self) -> None:
        payload = json.dumps({"command": 'print("ooi")'}).encode("utf-8")
        request = Request(
            f"{self.base}/api/terminal/command", method="POST", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
        output = "\n".join([*result["stdout"], *result["stderr"]])
        self.assertFalse(result["ok"])
        self.assertIn("python -c", output)
        self.assertNotIn("PRN", output)

    def test_terminal_resolves_python_from_the_computer(self) -> None:
        payload = json.dumps({"command": "python --version"}).encode("utf-8")
        request = Request(
            f"{self.base}/api/terminal/command", method="POST", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
        self.assertTrue(result["ok"], "\n".join(result["stderr"]))
        self.assertIn("Python", "\n".join([*result["stdout"], *result["stderr"]]))

    def test_python_resolution_prefers_the_project_virtual_environment(self) -> None:
        project = Path(self.temporary.name) / "python-project"
        executable = project / ".venv" / "Scripts" / "python.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"")
        self.assertEqual(find_python(project), executable.resolve())

    @unittest.skipUnless(shutil.which("git"), "Git não está instalado")
    def test_terminal_can_run_git_inside_workspace_repository(self) -> None:
        workspace = Path(__file__).resolve().parents[1]
        payload = json.dumps({"command": "git status --short --branch", "cwd": str(workspace)}).encode("utf-8")
        request = Request(
            f"{self.base}/api/terminal/command", method="POST", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=15) as response:
            result = json.load(response)
        self.assertTrue(result["ok"], "\n".join(result["stderr"]))
        self.assertIn("main", "\n".join(result["stdout"]))

    def test_dropzone_stores_history_and_serves_content(self) -> None:
        request = Request(
            f"{self.base}/api/dropzone/files",
            method="POST",
            data=b'{"ink": true}',
            headers={
                "Content-Type": "application/json",
                "X-File-Name": "dados.json",
                "X-File-Kind": "file",
            },
        )
        with urlopen(request, timeout=3) as response:
            stored = json.load(response)
        with urlopen(f"{self.base}/api/dropzone/history", timeout=3) as response:
            history = json.load(response)
        self.assertEqual(history["items"][0]["name"], "dados.json")
        with urlopen(f"{self.base}/api/dropzone/files/{stored['id']}/content", timeout=3) as response:
            self.assertEqual(response.read(), b'{"ink": true}')
        delete = Request(f"{self.base}/api/dropzone/files/{stored['id']}", method="DELETE")
        with urlopen(delete, timeout=3) as response:
            self.assertTrue(json.load(response)["ok"])
        with urlopen(f"{self.base}/api/dropzone/history", timeout=3) as response:
            self.assertEqual(json.load(response)["items"], [])

    def test_dropzone_receives_chunked_upload_and_byte_ranges(self) -> None:
        boundary = 8 * 1024 * 1024
        content = (b"A" * boundary) + b"parte-dois"
        create = Request(
            f"{self.base}/api/dropzone/uploads", method="POST",
            data=json.dumps({"name": "grande.bin", "type": "application/octet-stream", "size": len(content)}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(create, timeout=3) as response:
            upload = json.load(response)
        offset = 0
        for chunk in (content[:boundary], content[boundary:]):
            request = Request(
                f"{self.base}/api/dropzone/uploads/{upload['uploadId']}/chunk", method="POST", data=chunk,
                headers={"Content-Type": "application/octet-stream", "X-Upload-Offset": str(offset)},
            )
            with urlopen(request, timeout=3) as response:
                offset = json.load(response)["offset"]
        complete = Request(f"{self.base}/api/dropzone/uploads/{upload['uploadId']}/complete", method="POST", data=b"")
        with urlopen(complete, timeout=3) as response:
            stored = json.load(response)
        partial = Request(f"{self.base}/api/dropzone/files/{stored['id']}/content", headers={"Range": f"bytes={boundary}-{boundary + 4}"})
        with urlopen(partial, timeout=3) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), b"parte")

    def test_dropzone_preserves_folder_files_and_paths(self) -> None:
        create = Request(
            f"{self.base}/api/dropzone/folders", method="POST",
            data=json.dumps({"name": "projeto", "fileCount": 1, "size": 14}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(create, timeout=3) as response:
            folder = json.load(response)
        content = b"console.log(1)"
        upload_request = Request(
            f"{self.base}/api/dropzone/uploads", method="POST",
            data=json.dumps({
                "name": "app.js", "type": "text/javascript", "size": len(content),
                "folderId": folder["id"], "relativePath": "projeto/src/app.js",
            }).encode("utf-8"), headers={"Content-Type": "application/json"},
        )
        with urlopen(upload_request, timeout=3) as response:
            upload = json.load(response)
        chunk = Request(
            f"{self.base}/api/dropzone/uploads/{upload['uploadId']}/chunk", method="POST", data=content,
            headers={"Content-Type": "application/octet-stream", "X-Upload-Offset": "0"},
        )
        with urlopen(chunk, timeout=3):
            pass
        complete = Request(f"{self.base}/api/dropzone/uploads/{upload['uploadId']}/complete", method="POST", data=b"")
        with urlopen(complete, timeout=3) as response:
            uploaded_file = json.load(response)
        finish = Request(f"{self.base}/api/dropzone/folders/{folder['id']}/complete", method="POST", data=b"")
        with urlopen(finish, timeout=3):
            pass
        with urlopen(f"{self.base}/api/dropzone/folders/{folder['id']}", timeout=3) as response:
            manifest = json.load(response)
        self.assertEqual(manifest["files"][0]["path"], "projeto/src/app.js")
        with urlopen(f"{self.base}/api/dropzone/folders/{folder['id']}/files/{uploaded_file['id']}/content", timeout=3) as response:
            self.assertEqual(response.read(), content)

    def test_dropzone_does_not_finalize_an_incomplete_folder(self) -> None:
        create = Request(
            f"{self.base}/api/dropzone/folders", method="POST",
            data=json.dumps({"name": "incompleta", "fileCount": 2, "size": 10}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(create, timeout=3) as response:
            folder = json.load(response)
        finish = Request(f"{self.base}/api/dropzone/folders/{folder['id']}/complete", method="POST", data=b"")
        with self.assertRaises(HTTPError) as failed:
            urlopen(finish, timeout=3)
        self.assertEqual(failed.exception.code, 400)
        self.assertIn("Pasta incompleta", failed.exception.read().decode("utf-8"))

    def test_activity_is_persisted_marked_read_and_cleared(self) -> None:
        payload = json.dumps({
            "title": "Exportação concluída", "detail": "relatorio.pdf",
            "kind": "export", "level": "success",
            "actions": [{"label": "Abrir", "url": "http://127.0.0.1:8790/#modules"}],
        }).encode("utf-8")
        create = Request(
            f"{self.base}/api/activity", method="POST", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(create, timeout=3) as response:
            created = json.load(response)
        self.assertFalse(created["read"])
        self.assertEqual(created["actions"][0]["label"], "Abrir")
        with urlopen(f"{self.base}/api/activity", timeout=3) as response:
            self.assertEqual(json.load(response)["items"][0]["title"], "Exportação concluída")
        mark = Request(f"{self.base}/api/activity/read-all", method="POST", data=b"{}", headers={"Content-Type": "application/json"})
        with urlopen(mark, timeout=3) as response:
            self.assertEqual(json.load(response)["changed"], 1)
        clear = Request(f"{self.base}/api/activity", method="DELETE")
        with urlopen(clear, timeout=3) as response:
            self.assertEqual(json.load(response)["removed"], 1)

    def test_shared_presets_can_be_saved_listed_and_removed(self) -> None:
        payload = json.dumps({
            "name": "Card Instagram", "moduleIds": ["photos", "converter"],
            "data": {"width": 1080, "height": 1080},
        }).encode("utf-8")
        create = Request(f"{self.base}/api/presets", method="POST", data=payload, headers={"Content-Type": "application/json"})
        with urlopen(create, timeout=3) as response:
            preset = json.load(response)
        with urlopen(f"{self.base}/api/presets", timeout=3) as response:
            items = json.load(response)["items"]
        self.assertEqual(items[0]["data"]["width"], 1080)
        delete = Request(f"{self.base}/api/presets/{preset['id']}", method="DELETE")
        with urlopen(delete, timeout=3) as response:
            self.assertTrue(json.load(response)["ok"])

    def test_internal_clipboard_can_add_pin_and_remove_text(self) -> None:
        payload = json.dumps({"text": "texto entre módulos", "source": "Teste"}).encode("utf-8")
        create = Request(f"{self.base}/api/clipboard", method="POST", data=payload, headers={"Content-Type": "application/json"})
        with urlopen(create, timeout=3) as response:
            item = json.load(response)
        pin = Request(f"{self.base}/api/clipboard/{item['id']}/pin", method="POST", data=b'{"pinned": true}', headers={"Content-Type": "application/json"})
        with urlopen(pin, timeout=3) as response:
            self.assertTrue(json.load(response)["pinned"])
        with urlopen(f"{self.base}/api/clipboard", timeout=3) as response:
            self.assertEqual(json.load(response)["items"][0]["text"], "texto entre módulos")
        delete = Request(f"{self.base}/api/clipboard/{item['id']}", method="DELETE")
        with urlopen(delete, timeout=3) as response:
            self.assertTrue(json.load(response)["ok"])

    def test_module_snapshot_and_portable_export(self) -> None:
        snapshot = Request(
            f"{self.base}/api/module-data/writer", method="POST",
            data=json.dumps({"schemaVersion": 1, "data": {"documents": [{"title": "Teste"}]}}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(snapshot, timeout=3) as response:
            self.assertEqual(json.load(response)["moduleId"], "writer")
        with urlopen(f"{self.base}/api/module-data/writer", timeout=3) as response:
            self.assertEqual(json.load(response)["data"]["documents"][0]["title"], "Teste")
        with urlopen(f"{self.base}/api/portable/export?sections=settings,modules", timeout=5) as response:
            content = response.read()
            self.assertEqual(response.headers.get_content_type(), "application/zip")
        inspect = Request(f"{self.base}/api/portable/inspect", method="POST", data=content, headers={"Content-Type": "application/zip"})
        with urlopen(inspect, timeout=5) as response:
            payload = json.load(response)
        self.assertEqual(payload["format"], "ink-workspace-portable")
        self.assertEqual(payload["counts"]["modules"], 1)

    def test_modules_can_be_disabled_and_reloaded(self) -> None:
        disable = Request(f"{self.base}/api/modules/json/disable", method="POST", data=b"{}", headers={"Content-Type": "application/json"})
        with urlopen(disable, timeout=3) as response:
            self.assertIn("json", json.load(response)["disabled_modules"])
        with urlopen(f"{self.base}/api/modules", timeout=3) as response:
            modulo = next(item for item in json.load(response)["modules"] if item["id"] == "json")
        self.assertFalse(modulo["enabled"])
        reload_request = Request(f"{self.base}/api/modules/reload", method="POST", data=b"{}", headers={"Content-Type": "application/json"})
        with urlopen(reload_request, timeout=3) as response:
            self.assertTrue(json.load(response)["ok"])

    def test_blackbox_records_frontend_error_and_can_be_cleared(self) -> None:
        create = Request(
            f"{self.base}/api/blackbox", method="POST",
            data=json.dumps({"kind": "error", "level": "warning", "title": "Erro pequeno", "detail": "campo ausente", "moduleId": "writer"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(create, timeout=3) as response:
            self.assertEqual(json.load(response)["title"], "Erro pequeno")
        with urlopen(f"{self.base}/api/blackbox", timeout=3) as response:
            self.assertTrue(any(item["title"] == "Erro pequeno" for item in json.load(response)["items"]))
        clear = Request(f"{self.base}/api/blackbox", method="DELETE")
        with urlopen(clear, timeout=3) as response:
            self.assertGreaterEqual(json.load(response)["removed"], 1)


if __name__ == "__main__":
    unittest.main()
