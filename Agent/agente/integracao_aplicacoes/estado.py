"""Observações limitadas de disponibilidade; não replica dados das aplicações."""

from __future__ import annotations

from http.client import HTTPConnection, HTTPSConnection, HTTPException
from urllib.parse import urlparse

from agente.modelos import Observacao
from agente.percepcao import Percepcao

from .contrato import ContratoAplicacao
from .descoberta import DescobertaAplicacoes


def _saude_local(url: str | None, timeout: float = 0.7) -> bool | None:
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return None
    try:
        porta = parsed.port
    except ValueError:
        return None
    conexao = (HTTPSConnection if parsed.scheme == "https" else HTTPConnection)(
        parsed.hostname, porta, timeout=timeout)
    try:
        caminho = parsed.path or "/"
        conexao.request("GET", caminho)
        resposta = conexao.getresponse()
        resposta.read(2048)
        return resposta.status == 200
    except (OSError, HTTPException, TimeoutError):
        return False
    finally:
        conexao.close()


def observar_aplicacao(contrato: ContratoAplicacao) -> Observacao:
    instalada = contrato.pasta.is_dir() and (contrato.entrada is None or contrato.entrada.is_file())
    servico = _saude_local(contrato.health_url) if instalada else False
    return Observacao("estado_aplicacao", contrato.id, {
        "aplicacao": contrato.id,
        "disponivel": instalada,
        "aberta": None,
        "servico_ativo": servico,
        "versao": contrato.versao,
        "fornecedor": contrato.fornecedor,
    }, confianca=1.0 if servico is True or contrato.health_url is None else 0.75)


def registrar_perceptores(percepcao: Percepcao, descoberta: DescobertaAplicacoes) -> None:
    for contrato in descoberta.aplicacoes:
        percepcao.registrar(f"aplicacao:{contrato.id}",
                            lambda contrato=contrato: observar_aplicacao(contrato))
