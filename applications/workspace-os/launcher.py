from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.request import Request, urlopen

from workspace_os.server import WorkspaceServer, create_context, open_panel_later, start_background_modules
from workspace_os.doctor import WorkspaceDoctor, print_report
from workspace_os.origin import CoreOrigin
from workspace_os.settings import effective_module_urls


ROOT = Path(__file__).resolve().parent
ORIGIN = CoreOrigin.load(ROOT / "config" / "modules.json")
HOST = ORIGIN.host
PORT = ORIGIN.port
PANEL_URL = ORIGIN.url


def already_running() -> bool:
    try:
        with urlopen(f"{PANEL_URL}/api/health", timeout=0.5) as response:
            return response.status == 200
    except OSError:
        return False


def start_running_driver() -> None:
    try:
        with urlopen(f"{PANEL_URL}/api/session", timeout=2) as response:
            token = str(json.load(response).get("token", ""))
    except (OSError, ValueError):
        return
    request = Request(f"{PANEL_URL}/api/modules/drive2/start", data=b"{}", method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("X-Workspace-Token", token)
    request.add_header("Idempotency-Key", str(uuid.uuid4()))
    try:
        with urlopen(request, timeout=5):
            pass
    except OSError:
        pass


def chrome_executable() -> str | None:
    found = shutil.which("chrome.exe") or shutil.which("chrome")
    if found:
        return found
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    return next((str(path) for path in candidates if path.is_file()), None)


def open_chrome_later(delay: float = 0.8) -> None:
    def open_chrome() -> None:
        time.sleep(delay)
        executable = chrome_executable()
        if not executable:
            open_panel_later(0)
            return
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        subprocess.Popen(
            [executable, PANEL_URL],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )

    threading.Thread(target=open_chrome, daemon=True).start()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inicia o Workspace OS local.")
    parser.add_argument("--startup", action="store_true", help="Execução silenciosa iniciada pelo Windows.")
    parser.add_argument("--no-browser", action="store_true", help="Não abre o painel no navegador.")
    parser.add_argument("--portable", action="store_true", help="Guarda os dados ao lado do Workspace, ideal para pendrive.")
    parser.add_argument("--data-dir", type=Path, help="Pasta alternativa para os dados do Workspace.")
    parser.add_argument("--chrome", action="store_true", help="Abre o painel especificamente no Google Chrome.")
    parser.add_argument("--with-driver", action="store_true", help="Garante que o InkDriver local seja iniciado.")
    parser.add_argument("--doctor", action="store_true", help="Executa o diagnóstico local e encerra.")
    parser.add_argument("--json", action="store_true", help="Com --doctor, produz saída JSON para automação.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = ROOT
    data_dir = args.data_dir.resolve() if args.data_dir else ((root / "portable-data").resolve() if args.portable else None)
    if args.doctor:
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure:
                reconfigure(encoding="utf-8", errors="replace")
        report = WorkspaceDoctor(root, data_dir).run()
        if args.json:
            print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        else:
            print_report(report)
        return report.exit_code
    if already_running():
        if args.with_driver:
            start_running_driver()
        if not args.no_browser and not args.startup:
            (open_chrome_later if args.chrome else lambda delay=0: open_panel_later(delay, PANEL_URL))(0)
        return 0
    try:
        context = create_context(root, data_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("Não foi possível preparar o Workspace OS.", file=sys.stderr)
        print(f"Motivo: {exc}", file=sys.stderr)
        print("Execute workspace-doctor.cmd para localizar a configuração ou arquivo inválido.", file=sys.stderr)
        return 1
    settings_status = context.settings.load_status()
    if settings_status["recovered"]:
        print("Aviso: settings.json possui valores inválidos; defaults seguros foram usados.", file=sys.stderr)
        for issue in settings_status["issues"][:3]:
            print(f"- {issue}", file=sys.stderr)
    try:
        server = WorkspaceServer((HOST, PORT), context)
    except OSError as exc:
        print(f"Não foi possível usar http://{HOST}:{PORT}: {exc}", file=sys.stderr)
        return 1
    def start_modules() -> None:
        results = start_background_modules(context)
        failed = [result for result in results if not result.get("ok")]
        if failed:
            print("Workspace iniciado com módulos opcionais indisponíveis:", file=sys.stderr)
            for result in failed:
                print(f"- {result.get('module')}: {result.get('message')}", file=sys.stderr)
        if args.with_driver:
            settings = context.settings.load()
            driver_config = settings["module_configs"].get("drive2") or {}
            if driver_config.get("run_local", True):
                context.processes.start(
                    "drive2",
                    effective_module_urls(settings).get("drive2"),
                    driver_config,
                )

    threading.Thread(target=start_modules, daemon=True).start()
    should_open = not args.no_browser and (
        not args.startup or context.settings.load()["open_panel_on_start"]
    )
    if should_open:
        (open_chrome_later if args.chrome else lambda: open_panel_later(0.8, PANEL_URL))()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        context.processes.stop_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
