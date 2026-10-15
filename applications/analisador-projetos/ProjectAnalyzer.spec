# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for Project Analyzer.

Reusable notes:
- Change APP_NAME to reuse this file in another pywebview project.
- Keep frontend/ in datas if your UI is loaded from local HTML/CSS/JS files.
- Change or remove VERSION_FILE if you do not want Windows version metadata.
"""

from pathlib import Path

APP_NAME = "ProjectAnalyzer"
PROJECT_ROOT = Path(SPECPATH)
FRONTEND_DIR = PROJECT_ROOT / "frontend"
VERSION_FILE = PROJECT_ROOT / "build" / "windows_version_info.txt"


a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[(str(FRONTEND_DIR), "frontend")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(VERSION_FILE),
)
