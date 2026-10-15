from __future__ import annotations

import json
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from workspace_os.platform import GitProjects, PortableArchive


class GitProjectsTests(unittest.TestCase):
    def test_install_accepts_legacy_static_folder_and_creates_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ecosystem = Path(temporary)
            module = ecosystem / "meu-modulo"
            module.mkdir()
            (module / "index.html").write_text("<h1>Teste</h1>", encoding="utf-8")

            result = GitProjects(ecosystem).install({"type": "folder", "path": f'"{module}"'})

            self.assertTrue(result["ok"])
            manifest = json.loads((module / "ink-module.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["id"], "meu-modulo")
            self.assertEqual(manifest["entryFile"], "index.html")
            self.assertIn("Manifesto mínimo", result["message"])

    def test_install_rejects_non_web_folder_without_creating_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ecosystem = Path(temporary)
            module = ecosystem / "modulo-python"
            module.mkdir()
            (module / "run.py").write_text("print('ok')", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "ink-module.json"):
                GitProjects(ecosystem).install({"type": "folder", "path": str(module)})

            self.assertFalse((module / "ink-module.json").exists())

    def test_install_activates_pending_manifest_only_after_user_registration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            ecosystem = Path(temporary)
            module = ecosystem / "ink-notebook"
            module.mkdir()
            pending = module / "ink-module.json.pending"
            pending.write_text(json.dumps({
                "schemaVersion": 2, "id": "notebook", "name": "Ink Notebook",
                "category": "work", "description": "Notas locais.", "kind": "web-service",
                "url": "http://127.0.0.1:8001", "version": "1.0.0",
            }), encoding="utf-8")

            self.assertFalse((module / "ink-module.json").exists())
            result = GitProjects(ecosystem).install({"type": "folder", "path": str(module)})

            self.assertTrue(result["ok"])
            self.assertFalse(pending.exists())
            self.assertTrue((module / "ink-module.json").is_file())
            self.assertIn("pendente ativado", result["message"])

    def test_portable_archive_rejects_unsafe_member_paths(self) -> None:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("workspace-backup.json", json.dumps({"format": "ink-workspace-portable", "version": 1}))
            archive.writestr("../outside.bin", b"unsafe")
        with self.assertRaisesRegex(ValueError, "caminhos inválidos"):
            PortableArchive._read(output.getvalue())


if __name__ == "__main__":
    unittest.main()
