from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from workspace_os.registry import ModuleRegistry


class ModuleRegistryTests(unittest.TestCase):
    def test_project_registry_loads_unique_modules(self) -> None:
        workspace = Path(__file__).resolve().parents[1]
        registry = ModuleRegistry(workspace / "config/modules.json", workspace.parent)
        self.assertIn("organizer", registry.modules)
        self.assertIn("bridge", registry.modules)
        self.assertIn("notebook", registry.modules)
        self.assertTrue(registry.get("organizer").installed)
        self.assertEqual(len(registry.modules), len(list(workspace.parent.glob("*/ink-module.json"))))
        self.assertFalse(registry.discovery_errors)
        self.assertTrue(all(module.source == "manifest" for module in registry.modules.values()))

    def test_static_module_gets_local_http_url(self) -> None:
        workspace = Path(__file__).resolve().parents[1]
        registry = ModuleRegistry(workspace / "config/modules.json", workspace.parent)
        serialized = {item["id"]: item for item in registry.serialize()}
        self.assertEqual(serialized["json"]["url"], "http://127.0.0.1:8790/module/json/index.html")
        self.assertEqual(serialized["json"]["vendor"], "Ink-guginha")
        self.assertEqual(serialized["json"]["author"], "Ink-guginha")
        self.assertEqual(serialized["writer"]["name"], "InkWrite")
        self.assertEqual(serialized["writer"]["url"], "http://127.0.0.1:8790/module/writer/index.html")
        self.assertEqual(serialized["sheets"]["name"], "InkSheet")
        self.assertEqual(serialized["drive2"]["name"], "InkDriver")
        self.assertEqual(serialized["drive2"]["kind"], "web-service")
        self.assertEqual(serialized["drive2"]["url"], "http://127.0.0.1:8000")
        self.assertTrue(serialized["drive2"]["canStart"])
        self.assertEqual(serialized["notebook"]["url"], "http://127.0.0.1:8790/module/notebook/workspace/index.html")
        self.assertEqual(serialized["notebook"]["serviceUrl"], "http://127.0.0.1:8001")
        self.assertTrue(serialized["notebook"]["canStart"])

    def test_path_outside_ecosystem_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ecosystem = Path(temporary) / "ecosystem"
            config_dir = ecosystem / "workspace-os" / "config"
            config_dir.mkdir(parents=True)
            path = config_dir / "modules.json"
            path.write_text(
                json.dumps({"modules": [{"id": "bad-module", "path": "../../../outside"}]}),
                encoding="utf-8",
            )
            registry = ModuleRegistry(path, ecosystem)
            self.assertNotIn("bad-module", registry.modules)
            self.assertTrue(registry.discovery_errors)

    def test_duplicate_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ecosystem = Path(temporary)
            config_dir = ecosystem / "workspace-os" / "config"
            config_dir.mkdir(parents=True)
            path = config_dir / "modules.json"
            path.write_text(json.dumps({"modules": [{"id": "same"}, {"id": "same"}]}), encoding="utf-8")
            registry = ModuleRegistry(path, ecosystem)
            self.assertEqual(list(registry.modules), ["same"])
            self.assertTrue(registry.discovery_errors)

    def test_static_module_is_discovered_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ecosystem = Path(temporary)
            config_dir = ecosystem / "workspace-os" / "config"
            config_dir.mkdir(parents=True)
            config = config_dir / "modules.json"
            config.write_text(json.dumps({"modules": []}), encoding="utf-8")
            plugin = ecosystem / "ink-clock"
            plugin.mkdir()
            (plugin / "index.html").write_text("<h1>Clock</h1>", encoding="utf-8")
            (plugin / "ink-module.json").write_text(json.dumps({
                "id": "ink-clock", "name": "Ink Clock", "kind": "static-web",
                "entryFile": "index.html", "version": "1.0.0", "minCoreVersion": "0.1.0",
                "permissions": ["time:read"],
            }), encoding="utf-8")

            registry = ModuleRegistry(config, ecosystem)
            module = {item["id"]: item for item in registry.serialize()}["ink-clock"]
            self.assertEqual(module["url"], "http://127.0.0.1:8790/module/ink-clock/index.html")
            self.assertEqual(module["source"], "manifest")
            self.assertEqual(module["version"], "1.0.0")
            self.assertTrue(module["compatible"])
            self.assertEqual(module["permissions"], ["time:read"])

    def test_static_urls_use_the_central_core_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ecosystem = Path(temporary)
            config_dir = ecosystem / "workspace-os" / "config"
            config_dir.mkdir(parents=True)
            config = config_dir / "modules.json"
            config.write_text(json.dumps({"origin": {"host": "localhost", "port": 9911}, "modules": []}), encoding="utf-8")
            plugin = ecosystem / "ink-clock"
            plugin.mkdir()
            (plugin / "index.html").write_text("<h1>Clock</h1>", encoding="utf-8")
            (plugin / "ink-module.json").write_text(json.dumps({
                "id": "ink-clock", "name": "Ink Clock", "kind": "static-web", "entryFile": "index.html",
            }), encoding="utf-8")

            module = ModuleRegistry(config, ecosystem).serialize()[0]
            self.assertEqual(module["url"], "http://localhost:9911/module/ink-clock/index.html")

    def test_discovered_manifest_cannot_execute_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ecosystem = Path(temporary)
            config_dir = ecosystem / "workspace-os" / "config"
            config_dir.mkdir(parents=True)
            config = config_dir / "modules.json"
            config.write_text(json.dumps({"modules": []}), encoding="utf-8")
            plugin = ecosystem / "unsafe"
            plugin.mkdir()
            (plugin / "ink-module.json").write_text(json.dumps({
                "id": "unsafe-module", "kind": "static-web", "entryFile": "index.html",
                "command": ["powershell", "-Command", "echo no"],
            }), encoding="utf-8")

            registry = ModuleRegistry(config, ecosystem)
            self.assertNotIn("unsafe-module", registry.modules)
            self.assertTrue(registry.discovery_errors)

    def test_manifest_with_invalid_port_is_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ecosystem = Path(temporary)
            config_dir = ecosystem / "workspace-os" / "config"
            config_dir.mkdir(parents=True)
            config = config_dir / "modules.json"
            config.write_text(json.dumps({"modules": []}), encoding="utf-8")
            plugin = ecosystem / "broken-port"
            plugin.mkdir()
            (plugin / "ink-module.json").write_text(json.dumps({
                "id": "broken-port", "kind": "remote-web", "url": "http://127.0.0.1:99999",
            }), encoding="utf-8")

            registry = ModuleRegistry(config, ecosystem)
            self.assertNotIn("broken-port", registry.modules)
            self.assertTrue(any("porta inválida" in error for error in registry.discovery_errors))
            self.assertFalse(ModuleRegistry.is_reachable("http://127.0.0.1:99999"))

    def test_manifest_rejects_ambiguous_boolean_and_list_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ecosystem = Path(temporary)
            config_dir = ecosystem / "workspace-os" / "config"
            config_dir.mkdir(parents=True)
            config = config_dir / "modules.json"
            config.write_text(json.dumps({"trustedCommandModules": ["ambiguous"], "modules": []}), encoding="utf-8")
            plugin = ecosystem / "ambiguous"
            plugin.mkdir()
            (plugin / "ink-module.json").write_text(json.dumps({
                "id": "ambiguous", "kind": "web-service", "url": "http://127.0.0.1:9123",
                "command": ["tool"], "autoStart": "false",
                "capabilities": {"shortcuts": "save"},
            }), encoding="utf-8")
            registry = ModuleRegistry(config, ecosystem)
            self.assertNotIn("ambiguous", registry.modules)
            self.assertTrue(registry.discovery_errors)


if __name__ == "__main__":
    unittest.main()
