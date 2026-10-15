"""Canal local da janela Workspace para o processador existente da Yasmin."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlparse


HOST = "127.0.0.1"
PORTA = 45456
_LIMITE_CORPO = 4096


def criar_servidor_comandos(processar: Callable[[str], str], porta: int = PORTA,
                           estado: Callable[[], dict] | None = None) -> ThreadingHTTPServer:
    trava = threading.RLock()

    class Manipulador(BaseHTTPRequestHandler):
        def log_message(self, formato: str, *args: object) -> None:
            return

        def _json(self, codigo: HTTPStatus, dados: dict) -> None:
            corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(corpo)))
            self.end_headers()
            self.wfile.write(corpo)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._json(HTTPStatus.OK, {"ok": True, "status": "pronta", **(estado() if estado else {})})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "erro": "Rota não encontrada"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/command":
                self._json(HTTPStatus.NOT_FOUND, {"ok": False, "erro": "Rota não encontrada"})
                return
            # O navegador usa a API autenticada do Workspace OS. Este canal não
            # responde a páginas web nem aceita chamadas sem o cabeçalho do proxy.
            if (self.client_address[0] != HOST or self.headers.get("Origin")
                    or self.headers.get("X-Yasmin-Bridge") != "workspace-os"
                    or urlparse("//" + self.headers.get("Host", "")).hostname not in {HOST, "localhost"}):
                self._json(HTTPStatus.FORBIDDEN, {"ok": False, "erro": "Origem não autorizada"})
                return
            try:
                comprimento = int(self.headers.get("Content-Length", "0"))
                if not 0 < comprimento <= _LIMITE_CORPO:
                    raise ValueError("Tamanho do comando inválido")
                pedido = json.loads(self.rfile.read(comprimento).decode("utf-8"))
                texto = pedido.get("texto") if isinstance(pedido, dict) else None
                if not isinstance(texto, str) or not 0 < len(texto.strip()) <= 1000:
                    raise ValueError("Informe um comando de até 1000 caracteres")
            except (ValueError, UnicodeError, json.JSONDecodeError) as erro:
                self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "erro": str(erro)})
                return
            try:
                with trava:
                    resposta = processar(texto.strip())
                dados = resposta if isinstance(resposta, dict) else {"resposta": str(resposta or "Não recebi uma resposta verificável para esse comando.")}
                self._json(HTTPStatus.OK, {"ok": True, **dados})
            except Exception:
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR,
                           {"ok": False, "erro": "Não consegui executar o comando. Consulte o modo DEBUG."})

    servidor = ThreadingHTTPServer((HOST, porta), Manipulador)
    servidor.daemon_threads = True
    return servidor
