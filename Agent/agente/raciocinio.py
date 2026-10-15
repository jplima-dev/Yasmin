from __future__ import annotations

import re
import unicodedata
from typing import Protocol

from .modelos import Objetivo


class MecanismoRaciocinio(Protocol):
    def identificar(self, texto: str) -> Objetivo | None: ...


class RegrasDeterministicas:
    """Mecanismo substituível; reconhece somente tarefas que pode planejar."""

    def identificar(self, texto: str) -> Objetivo | None:
        normal = unicodedata.normalize("NFKD", texto.lower())
        normal = "".join(c for c in normal if not unicodedata.combining(c))
        if re.search(r"\b(?:nao|nunca|jamais)\b.{0,60}\b(?:analise|analisar|liste|listar|mostre|prepare|preparar|configure|organize|deixe|ajude)\b", normal):
            return None
        analise = re.search(r'\b(?:analise|analisar)\s+(?:o\s+)?projeto\s+(?:em|na pasta)\s+["“]([^"”]+)["”]', texto, re.IGNORECASE)
        if analise:
            return Objetivo(texto, parametros={"tipo": "analisar_projeto_ink",
                                              "caminho": analise.group(1),
                                              "perceptor": "aplicacao:project-analyzer"})
        if (re.search(r"\b(?:liste|mostre|quais|listar)\b.*\b(?:aplicativos|aplicacoes|modulos)\b", normal)
                and re.search(r"\b(?:ink|yasmin|yasm|workspace|disponiveis)\b", normal)):
            return Objetivo(texto, parametros={"tipo": "listar_aplicacoes_ink"})
        if (re.search(r"\b(?:prepare|preparar|configur[ea]|organize)\b.*\b(?:ambiente|programar|programacao)\b", normal)
                or re.search(r"\b(?:deixe|deixar|ajude|ajuda)\b.*\b(?:pronto|preparado)\b.*\b(?:codar|programar|desenvolver)\b", normal)):
            linguagem = "java" if "java" in normal else "geral"
            return Objetivo(texto, parametros={"tipo": "preparar_programacao", "linguagem": linguagem})
        return None
