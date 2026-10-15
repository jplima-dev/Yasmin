from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(BASE))

os.environ["YASM_VOICE_SERVER"] = "1"

import voz_yasm as voz


HOST = "127.0.0.1"
PORTA = 45455
CACHE = (BASE / ".voz_cache").resolve()
LIMITE_PEDIDO = 64 * 1024
TIMEOUT_PEDIDO = 5.0


def _receber_linha(conexao) -> bytes:
    dados = b""
    while len(dados) <= LIMITE_PEDIDO:
        parte = conexao.recv(min(8192, LIMITE_PEDIDO + 1 - len(dados)))
        if not parte:
            raise ValueError("Pedido incompleto.")
        dados += parte
        if b"\n" in dados:
            linha = dados.split(b"\n", 1)[0]
            if len(linha) <= LIMITE_PEDIDO:
                return linha
            break
    raise ValueError("Pedido excede o limite.")


def _processar(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {"ok": False, "erro": "pedido invalido"}
    if payload.get("acao") == "ping":
        return {"ok": True, "pronto": True}

    texto = payload.get("texto", "")
    voz_id = payload.get("voz", "kitsune:emilia")
    caminho = payload.get("arquivo", "")

    if not all(isinstance(valor, str) for valor in (texto, voz_id, caminho)):
        return {"ok": False, "erro": "pedido invalido"}
    texto, voz_id = texto.strip(), voz_id.strip()
    if not texto or len(texto) > 10000 or not voz_id.startswith("kitsune:") or not caminho:
        return {"ok": False, "erro": "pedido invalido"}

    try:
        arquivo = Path(caminho).resolve()
    except (OSError, ValueError):
        return {"ok": False, "erro": "arquivo invalido"}
    if arquivo.parent != CACHE or arquivo.suffix.casefold() != ".wav":
        return {"ok": False, "erro": "arquivo fora do cache"}

    ok = voz._gerar_wav_kitsune(texto, arquivo, voz_id)
    return {"ok": bool(ok)}


def main() -> None:
    CACHE.mkdir(exist_ok=True)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        servidor.bind((HOST, PORTA))
        servidor.listen(8)

        # A porta ja fica disponivel enquanto o ONNX termina de aquecer.
        voz._carregar_kitsune()

        while True:
            conexao, _ = servidor.accept()
            with conexao:
                # Um cliente desconectado ou que nao envia a mensagem inteira
                # nao pode bloquear todas as proximas falas indefinidamente.
                conexao.settimeout(TIMEOUT_PEDIDO)
                try:
                    pedido = json.loads(_receber_linha(conexao).decode("utf-8"))
                    resposta = _processar(pedido)
                except Exception as erro:
                    resposta = {"ok": False, "erro": type(erro).__name__}

                try:
                    conexao.sendall(
                        json.dumps(resposta, ensure_ascii=False).encode("utf-8") + b"\n"
                    )
                except OSError:
                    pass


if __name__ == "__main__":
    main()
