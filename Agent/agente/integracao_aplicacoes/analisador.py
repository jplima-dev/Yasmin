"""Adapter do backend público do Analisador de Projetos, de Ink-guginha."""

from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path

from agente.modelos import (Etapa, Observacao, ResultadoFerramenta,
                           ResultadoVerificacao, StatusVerificacao)

from .contrato import ContratoAplicacao


@lru_cache(maxsize=1)
def _classe_analisador(raiz: Path):
    pacote = raiz / "backend"
    especificacao = importlib.util.spec_from_file_location(
        "_yasm_ink_project_analyzer_backend", pacote / "__init__.py",
        submodule_search_locations=[str(pacote)],
    )
    if especificacao is None or especificacao.loader is None:
        raise RuntimeError("Backend do Analisador de Projetos indisponível")
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[especificacao.name] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo.ProjectAnalyzer


def analisar_projeto(contrato: ContratoAplicacao, caminho: str) -> ResultadoFerramenta:
    pasta = Path(caminho).expanduser().resolve()
    if not pasta.is_dir():
        return ResultadoFerramenta(False, erro=f"Pasta de projeto inexistente: {pasta}")
    resultado = _classe_analisador(contrato.pasta)().analyze(pasta)
    return ResultadoFerramenta(True, {
        "operacao": "analisar_projeto_ink",
        "aplicacao": contrato.id,
        "fornecedor": contrato.fornecedor,
        "mensagem": (f"Analisei {pasta.name}: {resultado['summary']['files']} arquivos "
                     f"e {resultado['summary']['lines']} linhas."),
        "projeto": resultado["project"],
        "resumo": resultado["summary"],
        "linguagens": resultado["languages"],
        "marcadores": resultado.get("markers", {}).get("counts", {}),
        "avisos": resultado.get("warnings", []),
    })


def verificar_analise(etapa: Etapa, observacao: Observacao) -> ResultadoVerificacao:
    dados = observacao.dados.get("resultado") or {}
    if not observacao.dados.get("sucesso"):
        return ResultadoVerificacao(StatusVerificacao.FALHA, 1.0,
                                    (observacao.dados.get("erro") or "Análise falhou",))
    pasta = Path(etapa.parametros["caminho"]).expanduser().resolve()
    resumo = dados.get("resumo") or {}
    projeto = dados.get("projeto") or {}
    contagens = (resumo.get("files"), resumo.get("directories"), resumo.get("lines"))
    if (pasta.is_dir() and projeto.get("path") == str(pasta)
            and all(isinstance(x, int) and x >= 0 for x in contagens)):
        return ResultadoVerificacao(StatusVerificacao.SUCESSO, 0.95,
                                    (f"Pasta existente: {pasta}",
                                     f"Arquivos contabilizados: {contagens[0]}"))
    return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.2,
                                ("Resultado da análise não corresponde à pasta observada",))
