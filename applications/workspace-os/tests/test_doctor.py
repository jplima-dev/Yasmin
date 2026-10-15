from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workspace_os.doctor import WorkspaceDoctor


class WorkspaceDoctorTests(unittest.TestCase):
    def test_doctor_reports_modules_and_corrupt_persisted_json(self) -> None:
        workspace = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary)
            (data_dir / "activity.json").write_text("{invalid", encoding="utf-8")
            report = WorkspaceDoctor(workspace, data_dir).run()
        codes = {check.code: check for check in report.checks}
        self.assertEqual(codes["MODULES_OK"].level, "ok")
        self.assertIn("MODULE_SDK_OK" if "MODULE_SDK_OK" in codes else "MODULE_SDK_WARNINGS", codes)
        self.assertEqual(codes["PERSISTED_JSON_INVALID"].level, "error")
        self.assertEqual(report.exit_code, 1)
        self.assertIn("Resultado:", report.render(ascii_only=True))


if __name__ == "__main__":
    unittest.main()
