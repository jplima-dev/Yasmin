"""Interpreta objetivos de desenvolvimento compostos antes das regras de comando simples."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .modelos import Objetivo
from .raciocinio import MecanismoRaciocinio


_CAMINHO = re.compile(r'["“]([^"”]+)["”]|\'([^\']+)\'')
_CAMINHO_SEM_ASPAS = re.compile(r"(?<!\w)(?:[a-zA-Z]:[\\/]|\.{1,2}[\\/])[^\s,;]+")


def _normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(letra for letra in base if not unicodedata.combining(letra))


def _caminhos(texto: str) -> list[tuple[str, int]]:
    encontrados = []
    intervalos = []
    for match in _CAMINHO.finditer(texto):
        valor = (match.group(1) or match.group(2) or "").strip()
        if valor and (Path(valor).is_absolute() or "\\" in valor or "/" in valor):
            encontrados.append((valor, match.start()))
            intervalos.append(match.span())
    for match in _CAMINHO_SEM_ASPAS.finditer(texto):
        if not any(inicio <= match.start() < fim for inicio, fim in intervalos):
            encontrados.append((match.group().rstrip(".!?"), match.start()))
    return sorted(encontrados, key=lambda item: item[1])


def _origem_destino(texto: str, caminhos: list[tuple[str, int]]) -> tuple[str, str]:
    origem, destino = caminhos[:2]
    antes_destino = _normalizar(texto[max(0, destino[1] - 55):destino[1]])
    antes_origem = _normalizar(texto[max(0, origem[1] - 55):origem[1]])
    if (re.search(r"(?:projeto|repositorio|codigo)(?:\s+(?:em|na pasta|no diretorio))?\s*$", antes_destino)
            and re.search(r"(?:destino|saida|salve|coloque|dentro da pasta|na pasta)\s*$", antes_origem)):
        return destino[0], origem[0]
    return origem[0], destino[0]


class RaciocinioDev:
    """Reconhece apenas fluxos cujos parâmetros e ferramentas são verificáveis."""

    def __init__(self, base: MecanismoRaciocinio):
        self.base = base

    def identificar(self, texto: str) -> Objetivo | None:
        pedido = re.sub(r"^(?:yasmin|yasm|yas)[,\s]+", "", texto.strip(), flags=re.I)
        caminhos = _caminhos(pedido)
        normal = _normalizar(pedido)
        criar = bool(re.search(r"\b(?:gere|gerar|gera|crie|criar|escreva|escrever|produza|monte|documente|faca|salve|exporte|exportar)\b", normal))
        leitor = bool(re.search(r"\b(?:leitor de projetos|leitor do projeto)\b", normal))
        if leitor and criar and re.search(r"\b(?:resumo|contexto|exporte|exportar)\b", normal):
            if len(caminhos) >= 2:
                origem, destino = _origem_destino(pedido, caminhos)
                return Objetivo(texto, parametros={"tipo": "exportar_contexto_projeto_ink",
                                                  "caminho": origem, "destino": destino,
                                                  "perceptor": "aplicacao:project-reader"})
            return None
        documento = bool(re.search(r"\b(?:readme|leia-me|documentacao)\b", normal)
                         or (re.search(r"\bdocumente\b", normal)
                             and re.search(r"\b(?:projeto|repositorio|codigo)\b", normal)))
        if documento and criar:
            if not caminhos:
                return None
            nome = re.search(r"\b(?:com\s+(?:o\s+)?nome|chamado|nomeado|salve\s+como|arquivo)\s+[\"“']?([\w.-]+)\b", pedido, re.I)
            nome_arquivo = nome.group(1) if nome else "README.md"
            if not nome_arquivo.lower().endswith(".md"):
                nome_arquivo += ".md"
            origem, destino = _origem_destino(pedido, caminhos) if len(caminhos) >= 2 else (caminhos[0][0], caminhos[0][0])
            if len(caminhos) == 1 and re.search(r"\b(?:este|esse)\s+projeto\b", normal):
                return None
            return Objetivo(texto, parametros={"tipo": "gerar_readme_projeto",
                                              "caminho": origem, "destino": destino,
                                              "nome": nome_arquivo,
                                              "perceptor": "aplicacao:project-analyzer"})
        if (criar and len(caminhos) >= 2 and re.search(r"\b(?:resumo|relatorio)\b", normal)
                and re.search(r"\b(?:projeto|repositorio)\b", normal)):
            origem, destino = _origem_destino(pedido, caminhos)
            return Objetivo(texto, parametros={"tipo": "resumir_projeto_em_arquivo",
                                              "caminho": origem, "destino": destino,
                                              "perceptor": "aplicacao:project-analyzer"})
        leitura = bool(re.search(r"\b(?:leia|ler|le|analise|analisar|analisa|entenda|explique|explica|descreva|descrever|resuma|resumir)\b", normal))
        finalidade = bool(re.search(r"\b(?:o que (?:ele |esse projeto )?faz|que faz|pra que serve|para que serve|finalidade|proposito|objetivo|explique|explica|descreva|descrever|resuma|resumo|entenda)\b", normal))
        if leitura and re.search(r"\b(?:projeto|repositorio|codigo)\b", normal) and finalidade:
            if caminhos:
                return Objetivo(texto, parametros={"tipo": "descrever_projeto",
                                                  "caminho": caminhos[0][0],
                                                  "perceptor": "aplicacao:project-analyzer"})
            return None
        return self.base.identificar(texto)
