"""Valida propostas de etapas contra as ferramentas reais antes de planejar."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import re
import unicodedata

from .ferramentas import RegistroFerramentas
from .modelos import Objetivo, Risco


def catalogo_planejavel(registro: RegistroFerramentas) -> dict[str, dict]:
    """Expõe ao raciocínio só ferramentas registradas e verificáveis."""
    return {item.nome: {"descricao": item.descricao,
                        "parametros": list(item.parametros), "risco": item.risco.value}
            for item in registro.listar()
            if item.verificacao and item.risco != Risco.ALTO}


def objetivo_de_proposta(texto: str, proposta: Any,
                        registro: RegistroFerramentas) -> Objetivo | None:
    """Rejeita nomes inventados, parâmetros extras e caminhos não ditos pelo usuário."""
    if not isinstance(proposta, dict):
        return None
    etapas = proposta.get("etapas")
    if not isinstance(etapas, list) or not 1 <= len(etapas) <= 6:
        return None
    permitidas = catalogo_planejavel(registro)
    validadas = []
    for item in etapas:
        if not isinstance(item, dict) or set(item) != {"ferramenta", "parametros"}:
            return None
        nome, parametros = item["ferramenta"], item["parametros"]
        if not isinstance(nome, str) or nome not in permitidas or not isinstance(parametros, dict):
            return None
        ferramenta = registro.obter(nome)
        if set(parametros) != set(ferramenta.parametros):
            return None
        for chave, valor in parametros.items():
            if not isinstance(valor, str) or not valor.strip() or len(valor) > 500:
                return None
            if chave in {"caminho", "destino"}:
                if not Path(valor).is_absolute() or valor.casefold() not in texto.casefold():
                    return None
            elif chave == "nome" and nome == "escrever_resumo_projeto":
                if not valor.lower().endswith(".md"):
                    return None
                pedido_normal = unicodedata.normalize("NFKD", texto.casefold())
                pedido_normal = "".join(letra for letra in pedido_normal
                                         if not unicodedata.combining(letra))
                padrao = ((valor.lower() == "readme.md" and "readme" in texto.casefold())
                          or (valor.lower() == "resumo_projeto.md" and re.search(
                              r"\b(?:resumo|relatorio|inventario|documentacao|guia)\b",
                              pedido_normal)))
                if not padrao and valor.casefold() not in texto.casefold():
                    return None
            elif chave in {"nome", "aplicacao"} and valor.casefold() not in texto.casefold():
                if not (chave == "aplicacao" and valor == "project-reader"
                        and "leitor de projetos" in texto.casefold()):
                    return None
        validadas.append({"ferramenta": nome, "parametros": dict(parametros)})
    normal = unicodedata.normalize("NFKD", texto.casefold())
    normal = "".join(letra for letra in normal if not unicodedata.combining(letra))
    nomes = {item["ferramenta"] for item in validadas}
    exigencias = (
        (r"\b(?:abra|abre|abrir|inicie|iniciar)\b",
         {"abrir_aplicacao_ink", "abrir_aplicativo"}),
        (r"\b(?:pesquise|pesquisar|busque na internet)\b", {"pesquisar_web"}),
        (r"\b(?:grave|salve|crie|criar|gere|gerar|escreva|produza|documente)\b"
         r".*\b(?:arquivo|readme|documento|documentacao|resumo|relatorio)\b",
         {"escrever_resumo_projeto", "exportar_contexto_projeto_ink"}),
    )
    if any(re.search(padrao, normal) and not (nomes & aceitas)
           for padrao, aceitas in exigencias):
        return None
    return Objetivo(texto, parametros={"tipo": "plano_ferramentas", "etapas": validadas})
