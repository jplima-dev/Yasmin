"""Consultas da API pública do Ink Notebook, sem acessar seu banco interno."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from agente.modelos import (Etapa, Observacao, ResultadoFerramenta,
                           ResultadoVerificacao, StatusVerificacao)

from .contrato import ContratoAplicacao
from .estado import _saude_local


def _endereco_cadernos(contrato: ContratoAplicacao) -> str:
    if not contrato.health_url:
        raise ValueError("Ink Notebook sem endereço de serviço")
    parsed = urlparse(contrato.health_url)
    return urlunparse(parsed._replace(path="/api/notebooks", params="", query="", fragment=""))


def _consultar(contrato: ContratoAplicacao) -> list[dict]:
    if _saude_local(contrato.health_url) is not True:
        raise ConnectionError("Serviço do Ink Notebook não está ativo")
    from .abertura import _abridor, _url_local
    import json

    url = _endereco_cadernos(contrato)
    if not _url_local(url):
        raise ValueError("Endereço do Ink Notebook não é local")
    with _abridor.open(url, timeout=1.0) as resposta:
        if resposta.status != 200:
            raise ConnectionError(f"Ink Notebook respondeu HTTP {resposta.status}")
        bruto = resposta.read(1024 * 1024 + 1)
        if len(bruto) > 1024 * 1024:
            raise ValueError("Lista de cadernos excede 1 MB")
        dados = json.loads(bruto)
    if not isinstance(dados, list) or any(not isinstance(item, dict) for item in dados):
        raise ValueError("Lista de cadernos inválida")
    return dados


def listar_cadernos(contrato: ContratoAplicacao) -> ResultadoFerramenta:
    try:
        cadernos = _consultar(contrato)
        resumo = []
        for item in cadernos:
            if not isinstance(item.get("id"), int) or not isinstance(item.get("name"), str):
                raise ValueError("Caderno sem identificação válida")
            resumo.append({"id": item["id"], "nome": item["name"],
                           "documentos": int(item.get("doc_count", 0))})
        return ResultadoFerramenta(True, {
            "operacao": "listar_cadernos_ink", "aplicacao": contrato.id,
            "fornecedor": contrato.fornecedor, "total": len(resumo), "cadernos": resumo,
            "mensagem": f"Encontrei {len(resumo)} caderno(s) no Ink Notebook.",
        })
    except (OSError, ValueError, TypeError, ConnectionError) as erro:
        return ResultadoFerramenta(False, erro=f"Não consegui consultar o Ink Notebook: {erro}")


def verificar_cadernos(contrato: ContratoAplicacao, etapa: Etapa,
                       observacao: Observacao) -> ResultadoVerificacao:
    dados = observacao.dados.get("resultado") or {}
    if not observacao.dados.get("sucesso"):
        return ResultadoVerificacao(StatusVerificacao.FALHA, 1.0,
                                    (str(observacao.dados.get("erro") or "Consulta falhou"),))
    try:
        atuais = _consultar(contrato)
        ids = [item["id"] for item in atuais]
        recebidos = [item["id"] for item in dados.get("cadernos", [])]
        if dados.get("total") == len(atuais) and ids == recebidos:
            return ResultadoVerificacao(StatusVerificacao.SUCESSO, 0.95,
                                        (f"API do Ink Notebook confirmou {len(ids)} cadernos",))
        return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.5,
                                    ("A lista mudou entre execução e verificação",))
    except (OSError, ValueError, TypeError, KeyError, ConnectionError) as erro:
        return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.3,
                                    (f"Não foi possível verificar o Ink Notebook: {erro}",))
