from __future__ import annotations

import os
import runpy
import socket
import sys
from pathlib import Path


def discover_lan_address() -> str | None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("1.1.1.1", 53))
        return str(probe.getsockname()[0])
    except OSError:
        try:
            candidate = socket.gethostbyname(socket.gethostname())
            return candidate if not candidate.startswith("127.") else None
        except OSError:
            return None
    finally:
        probe.close()


def main() -> None:
    bridge_root = Path.cwd().resolve()
    entry_point = bridge_root / "run.py"
    if not (bridge_root / "core").is_dir() or not entry_point.is_file():
        raise SystemExit("Execute este adaptador com a pasta do Bridge como diretório de trabalho.")
    if "BRIDGE_PUBLIC_URL" not in os.environ:
        address = discover_lan_address()
        port = int(os.environ.get("BRIDGE_PORT", "8876"))
        os.environ["BRIDGE_PUBLIC_URL"] = (
            f"http://{address}:{port}" if address else f"http://127.0.0.1:{port}"
        )
    sys.path.insert(0, str(bridge_root))
    port = int(os.environ.get("BRIDGE_PORT", "8876"))
    print(f"Painel local: http://127.0.0.1:{port}", flush=True)
    print(f"Outros aparelhos: {os.environ['BRIDGE_PUBLIC_URL']}", flush=True)
    runpy.run_path(str(entry_point), run_name="__main__")


if __name__ == "__main__":
    main()
