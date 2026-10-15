from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from workspace_os.module_sdk import ModuleSpec, create_module, validate_modules


class ModuleSdkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace-os"
        self.config = self.workspace / "config" / "modules.json"
        self.config.parent.mkdir(parents=True)
        self.config.write_text(json.dumps({
            "schemaVersion": 2,
            "origin": {"scheme": "http", "host": "127.0.0.1", "port": 8790},
            "trustedCommandModules": [],
            "moduleOrder": [],
            "modules": [],
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def spec(module_id: str = "sample-tool", **changes: object) -> ModuleSpec:
        values = {
            "name": "Ferramenta de Exemplo",
            "module_id": module_id,
            "description": "Módulo criado pelo SDK.",
            "module_type": "static-web",
            "include_preferences": True,
            "include_backup": True,
        }
        values.update(changes)
        return ModuleSpec(**values)

    def test_valid_module_is_created_and_validated(self) -> None:
        result = create_module(self.spec(), self.root, self.config)
        self.assertTrue(result.manifest_path.is_file())
        self.assertTrue((result.module_path / "app.js").is_file())
        report = validate_modules(self.root, self.config)
        self.assertEqual(report.exit_code, 0, report.render(ascii_only=True))
        self.assertEqual(report.modules[0].module_id, "sample-tool")
        config = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertIn("sample-tool", config["moduleOrder"])

    def test_duplicate_id_is_reported_for_both_modules(self) -> None:
        first = create_module(self.spec(), self.root, self.config).module_path
        second = self.root / "other-folder"
        second.mkdir()
        (second / "ink-module.json").write_bytes((first / "ink-module.json").read_bytes())
        (second / "index.html").write_text("<!doctype html>", encoding="utf-8")
        report = validate_modules(self.root, self.config)
        duplicates = [
            issue for module in report.modules for issue in module.issues
            if issue.code == "DUPLICATE_ID"
        ]
        self.assertEqual(len(duplicates), 2)
        self.assertEqual(report.exit_code, 1)

    def test_invalid_id_is_rejected_before_writing(self) -> None:
        with self.assertRaises(ValueError):
            create_module(self.spec("../unsafe"), self.root, self.config)
        self.assertEqual([path.name for path in self.root.iterdir()], ["workspace-os"])

    def test_missing_entry_file_is_reported(self) -> None:
        module = create_module(self.spec(), self.root, self.config).module_path
        (module / "index.html").unlink()
        report = validate_modules(self.root, self.config)
        codes = {issue.code for issue in report.modules[0].issues}
        self.assertIn("ENTRY_MISSING", codes)

    def test_invalid_manifest_is_isolated(self) -> None:
        module = self.root / "broken-module"
        module.mkdir()
        (module / "ink-module.json").write_text("{invalid", encoding="utf-8")
        report = validate_modules(self.root, self.config)
        self.assertEqual(len(report.modules), 1)
        self.assertEqual(report.modules[0].issues[0].code, "MANIFEST_JSON")
        self.assertEqual(report.exit_code, 1)

    def test_existing_module_is_never_overwritten(self) -> None:
        result = create_module(self.spec(), self.root, self.config)
        marker = result.module_path / "keep.txt"
        marker.write_text("preservar", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            create_module(self.spec(), self.root, self.config)
        self.assertEqual(marker.read_text(encoding="utf-8"), "preservar")

    def test_node_and_python_service_templates_follow_real_contract(self) -> None:
        node = create_module(self.spec(
            "node-tool", module_type="node-service", port=8801,
            managed_service=True, auto_start=False, name="Node `seguro` ${process.exit()}",
        ), self.root, self.config)
        python = create_module(self.spec(
            "python-tool", module_type="python-service", port=8802,
            managed_service=True, auto_start=False, name='Python "seguro"',
        ), self.root, self.config)
        self.assertTrue((node.module_path / "server.js").is_file())
        self.assertTrue((node.module_path / "package.json").is_file())
        self.assertTrue((python.module_path / "server.py").is_file())
        subprocess.run(["node", "--check", str(node.module_path / "server.js")], check=True)
        subprocess.run(["node", "--check", str(node.module_path / "app.js")], check=True)
        subprocess.run([sys.executable, "-m", "py_compile", str(python.module_path / "server.py")], check=True)
        report = validate_modules(self.root, self.config)
        self.assertEqual(report.exit_code, 0, report.render(ascii_only=True))
        config = json.loads(self.config.read_text(encoding="utf-8"))
        self.assertIn("node-tool", config["trustedCommandModules"])
        self.assertIn("python-tool", config["trustedCommandModules"])

    def test_web_service_shell_accepts_service_url_without_public_url(self) -> None:
        module = self.root / "isolated-service"
        (module / "workspace").mkdir(parents=True)
        (module / "workspace" / "index.html").write_text("<!doctype html>", encoding="utf-8")
        (module / "ink-module.json").write_text(json.dumps({
            "schemaVersion": 2, "id": "isolated-service", "name": "Serviço Isolado",
            "category": "work", "kind": "web-service", "serviceUrl": "http://127.0.0.1:8123",
            "healthUrl": "http://127.0.0.1:8123/health", "entryFile": "workspace/index.html",
            "version": "1.0.0", "minCoreVersion": "0.3.0",
        }), encoding="utf-8")

        report = validate_modules(self.root, self.config)
        self.assertEqual(report.exit_code, 0, report.render(ascii_only=True))


if __name__ == "__main__":
    unittest.main()
