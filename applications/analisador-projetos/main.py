from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

from backend import ProjectAnalyzer


def _settings_file() -> Path:
    """Return a writable per-user settings file that also works in a PyInstaller .exe."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "ProjectAnalyzer" / "settings.json"


def _load_language() -> str:
    path = _settings_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        language = data.get("language", "en")
        return language if language in {"pt", "en"} else "en"
    except (OSError, json.JSONDecodeError, TypeError, AttributeError):
        return "en"


def _save_language(language: str) -> None:
    path = _settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"language": language}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


class DesktopApi:
    """Small, serialization-safe API exposed to JavaScript.

    pywebview recursively inspects public attributes on ``js_api`` objects. Keep
    backend state private and never retain the native Window instance here.
    """

    def __init__(self) -> None:
        self._analyzer = ProjectAnalyzer()

    def get_settings(self) -> dict[str, Any]:
        """Return persisted UI settings."""
        return {
            "ok": True,
            "language": _load_language(),
            "settings_path": str(_settings_file()),
        }

    def set_language(self, language: str) -> dict[str, Any]:
        """Persist the selected interface language."""
        if language not in {"pt", "en"}:
            return {"ok": False, "error": "Unsupported language."}

        try:
            _save_language(language)
            return {"ok": True, "language": language}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    def select_project(self) -> dict[str, Any]:
        """Open a native folder picker and immediately analyze the selected folder."""
        import webview

        if not webview.windows:
            return {"ok": False, "error": "Application window is not ready."}

        window = webview.windows[0]
        result = window.create_file_dialog(webview.FileDialog.FOLDER, allow_multiple=False)
        if not result:
            return {"ok": False, "cancelled": True}

        selected = result[0] if isinstance(result, (tuple, list)) else result
        return self.analyze_path(str(selected))

    def analyze_path(self, path: str) -> dict[str, Any]:
        try:
            data = self._analyzer.analyze(path)
            return {"ok": True, "data": data}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def run_cli(path: str, pretty: bool = True) -> int:
    analyzer = ProjectAnalyzer()
    try:
        result = analyzer.analyze(path)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if pretty:
        summary = result["summary"]
        print(f"Project: {result['project']['name']}")
        print(f"Path: {result['project']['path']}")
        print()
        print(f"Files: {summary['files']}")
        print(f"Directories: {summary['directories']}")
        print(f"Lines: {summary['lines']}")
        print(f"Size: {summary['size']} bytes")
        print()
        print("Languages:")
        languages = sorted(
            result["languages"].items(),
            key=lambda item: item[1]["lines"],
            reverse=True,
        )
        if not languages:
            print("  No recognized source languages.")
        for language, stats in languages:
            print(
                f"  {language}: {stats['lines']} lines, "
                f"{stats['files']} files, {stats['percent_by_lines']:.2f}% by lines"
            )

        markers = result.get("markers", {})
        counts = markers.get("counts", {})
        print()
        print("Code markers:")
        print(
            f"  TODO: {counts.get('TODO', 0)} | "
            f"FIXME: {counts.get('FIXME', 0)} | "
            f"HACK: {counts.get('HACK', 0)}"
        )
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def run_gui(debug: bool = False) -> int:
    try:
        import webview
    except ImportError:
        print(
            "pywebview is not installed. Run: pip install -r requirements.txt\n"
            "You can still test the analyzer with: python main.py --cli PATH",
            file=sys.stderr,
        )
        return 1

    frontend = Path(__file__).resolve().parent / "frontend" / "index.html"
    api = DesktopApi()
    window = webview.create_window(
        "Project Analyzer",
        url=str(frontend),
        width=1280,
        height=800,
        min_size=(960, 640),
        maximized=True,
        background_color="#0b0f17",
        text_select=True,
    )
    window.expose(
        api.select_project,
        api.analyze_path,
        api.get_settings,
        api.set_language,
    )
    webview.start(debug=debug)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a source-code project directory.")
    parser.add_argument("--cli", metavar="PATH", help="Analyze PATH in the terminal instead of opening the GUI.")
    parser.add_argument("--json", action="store_true", help="With --cli, print the complete result as JSON.")
    parser.add_argument("--debug", action="store_true", help="Enable pywebview debug mode.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.cli:
        return run_cli(args.cli, pretty=not args.json)
    return run_gui(debug=args.debug)


if __name__ == "__main__":
    raise SystemExit(main())
