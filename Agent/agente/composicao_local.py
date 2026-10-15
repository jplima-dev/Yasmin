"""Compõe pedidos de projeto com operações do registro, sem fornecedor de IA."""

from __future__ import annotations

import re
from pathlib import Path

from .ferramentas import RegistroFerramentas
from .modelos import Objetivo
from .pedidos_dev import _caminhos, _normalizar, _origem_destino
from .planos_ferramentas import objetivo_de_proposta


def compor_projeto(texto: str, registro: RegistroFerramentas) -> Objetivo | None:
    """Aceita sequências completas de inspeção, leitura, listagem e documentação."""
    normal = _normalizar(texto)
    if not re.search(r"\b(?:projeto|repositorio|codigo)\b", normal):
        return None
    if re.search(r"\b(?:execute|executar|rode|rodar|compile|compilar|teste|testar|apague|exclua)\b", normal):
        return None
    caminhos = _caminhos(texto)
    if not caminhos or any(not Path(valor).is_absolute() for valor, _ in caminhos[:2]):
        return None
    origem, destino = (_origem_destino(texto, caminhos) if len(caminhos) >= 2
                       else (caminhos[0][0], caminhos[0][0]))
    if len(caminhos) == 1 and re.search(r"\b(?:este|esse)\s+projeto\b", normal):
        return None

    achados: list[tuple[int, str, dict[str, str]]] = []

    def adicionar(padrao: str, ferramenta: str, parametros: dict[str, str]) -> None:
        encontrado = re.search(padrao, normal)
        if encontrado:
            achados.append((encontrado.start(), ferramenta, parametros))

    abertura = re.search(r"\b(?:abra|abre|abrir|inicie)\b", normal)
    if abertura:
        if not re.search(r"\bleitor (?:de|do) projetos\b", normal):
            return None
        achados.append((abertura.start(), "abrir_aplicacao_ink", {"aplicacao": "project-reader"}))
    adicionar(r"\b(?:analise|analisar|inspecione|examine|avalie|mapeie|inventario|inventarie|levantamento)\b",
             "analisar_projeto_ink", {"caminho": origem})
    adicionar(r"\b(?:leia|ler|entenda|explique|descreva)\b",
             "descrever_projeto", {"caminho": origem})
    adicionar(r"\b(?:liste|listar|enumere|mostre)\b.{0,35}\barquivos\b",
             "listar_arquivos_projeto_ink", {"caminho": origem})
    if re.search(r"\b(?:exporte|exportar|extraia)\b", normal):
        if len(caminhos) < 2 or not re.search(r"\b(?:leitor|contexto)\b", normal):
            return None
        adicionar(r"\b(?:exporte|exportar|extraia)\b",
                 "exportar_contexto_projeto_ink", {"caminho": origem, "destino": destino})
    escrita = re.search(r"\b(?:grave|salve|escreva|produza|crie|criar|gere|gerar|documente)\b", normal)
    artefato = re.search(r"\b(?:readme|documentacao|resumo|relatorio|guia)\b|\.md\b", normal)
    if escrita:
        if not artefato:
            return None
        sem_caminhos = texto
        for valor, _ in caminhos:
            sem_caminhos = sem_caminhos.replace(valor, " ")
        nome = re.search(r"\b([\w.-]+\.md)\b", sem_caminhos, re.I)
        nome_arquivo = (nome.group(1) if nome else
                        "README.md" if re.search(r"\breadme\b", normal) else "resumo_projeto.md")
        achados.append((escrita.start(), "escrever_resumo_projeto",
                        {"caminho": origem, "destino": destino, "nome": nome_arquivo}))
    if not achados:
        return None
    achados.sort(key=lambda item: item[0])
    proposta = {"etapas": [{"ferramenta": nome, "parametros": parametros}
                           for _, nome, parametros in achados]}
    return objetivo_de_proposta(texto, proposta, registro)
