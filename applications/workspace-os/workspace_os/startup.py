from __future__ import annotations

import os
import sys
from pathlib import Path


class WindowsStartup:
    filename = "WorkspaceOS.vbs"

    def __init__(self, launcher_path: Path, startup_dir: Path | None = None) -> None:
        self.launcher_path = launcher_path.resolve()
        if startup_dir is None:
            app_data = os.environ.get("APPDATA")
            if not app_data:
                raise RuntimeError("A pasta APPDATA do Windows não foi encontrada.")
            startup_dir = Path(app_data) / "Microsoft/Windows/Start Menu/Programs/Startup"
        self.startup_dir = startup_dir.resolve()
        self.path = self.startup_dir / self.filename

    @property
    def supported(self) -> bool:
        return os.name == "nt"

    def status(self) -> dict[str, object]:
        enabled = self.path.exists()
        valid = False
        if enabled:
            try:
                valid = str(self.launcher_path) in self.path.read_text(encoding="utf-8")
            except OSError:
                valid = False
        return {"supported": self.supported, "enabled": enabled and valid, "path": str(self.path)}

    def enable(self) -> dict[str, object]:
        if not self.supported:
            raise RuntimeError("A inicialização automática desta versão é exclusiva do Windows.")
        python = Path(sys.executable).resolve()
        pythonw = python.with_name("pythonw.exe")
        if not pythonw.exists():
            pythonw = python
        command = f'"{pythonw}" "{self.launcher_path}" --startup'
        vb_command = command.replace('"', '""')
        content = (
            "Set workspaceShell = CreateObject(\"WScript.Shell\")\n"
            f'workspaceShell.Run "{vb_command}", 0, False\n'
            "Set workspaceShell = Nothing\n"
        )
        self.startup_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(self.path)
        return self.status()

    def disable(self) -> dict[str, object]:
        if self.path.exists():
            self.path.unlink()
        return self.status()
