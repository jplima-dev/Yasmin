from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from workspace_os.startup import WindowsStartup


@unittest.skipUnless(os.name == "nt", "Inicialização específica do Windows")
class WindowsStartupTests(unittest.TestCase):
    def test_enable_and_disable_use_current_user_startup_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            launcher = root / "launcher.py"
            launcher.write_text("pass\n", encoding="utf-8")
            startup = WindowsStartup(launcher, root / "Startup")
            enabled = startup.enable()
            self.assertTrue(enabled["enabled"])
            content = startup.path.read_text(encoding="utf-8")
            self.assertIn(str(launcher.resolve()), content)
            self.assertIn("--startup", content)
            disabled = startup.disable()
            self.assertFalse(disabled["enabled"])
            self.assertFalse(startup.path.exists())


if __name__ == "__main__":
    unittest.main()

