"""Abre o Workspace OS como janela da Yasmin sem mudar os aplicativos."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


RAIZ = Path(__file__).resolve().parents[2]
WORKSPACE = RAIZ / "applications" / "workspace-os"


def _origem() -> str:
    dados = json.loads((WORKSPACE / "config" / "modules.json").read_text(encoding="utf-8"))["origin"]
    host, porta = dados["host"], int(dados["port"])
    if dados["scheme"] != "http" or host not in {"127.0.0.1", "localhost"} or not 1 <= porta <= 65535:
        raise ValueError("Origem local do Workspace OS inválida")
    return f"http://{host}:{porta}"


def _ativo(origem: str) -> bool:
    try:
        with urlopen(origem + "/api/health", timeout=0.4) as resposta:
            return json.load(resposta).get("status") == "ok"
    except (OSError, ValueError, URLError):
        return False


def _navegador_aplicativo() -> str | None:
    candidatos = [
        shutil.which("msedge.exe"), shutil.which("msedge"),
        shutil.which("chrome.exe"), shutil.which("chrome"),
    ]
    if os.name == "nt":
        for ambiente, relativo in (
            ("PROGRAMFILES(X86)", "Microsoft/Edge/Application/msedge.exe"),
            ("PROGRAMFILES", "Microsoft/Edge/Application/msedge.exe"),
            ("LOCALAPPDATA", "Microsoft/Edge/Application/msedge.exe"),
            ("PROGRAMFILES", "Google/Chrome/Application/chrome.exe"),
            ("PROGRAMFILES(X86)", "Google/Chrome/Application/chrome.exe"),
            ("LOCALAPPDATA", "Google/Chrome/Application/chrome.exe"),
        ):
            if os.environ.get(ambiente):
                candidatos.append(str(Path(os.environ[ambiente]) / relativo))
    return next((c for c in candidatos if c and Path(c).is_file()), None)


def abrir_janela() -> bool:
    """Inicia o serviço existente, espera saúde real e abre janela de app."""
    origem = _origem()
    if not _ativo(origem):
        launcher = WORKSPACE / "launcher.py"
        if not launcher.is_file():
            return False
        subprocess.Popen([sys.executable, str(launcher), "--no-browser"],
                         cwd=WORKSPACE, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        limite = time.monotonic() + 5
        while time.monotonic() < limite and not _ativo(origem):
            time.sleep(0.15)
        if not _ativo(origem):
            return False
    navegador = _navegador_aplicativo()
    if navegador:
        subprocess.Popen([navegador, f"--app={origem}/", "--new-window"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return True
    return bool(webbrowser.open_new(origem + "/"))
