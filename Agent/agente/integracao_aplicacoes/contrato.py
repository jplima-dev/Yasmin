"""Lê contratos declarativos sem executar código de manifestos."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agente.modelos import Risco


IDENTIFICADOR = re.compile(r"^[a-z][a-z0-9-]{1,39}$")
NOME_FERRAMENTA = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
FORNECEDOR = "Ink-guginha"


@dataclass(frozen=True)
class OperacaoAplicacao:
    nome: str
    descricao: str
    parametros: tuple[str, ...]
    risco: Risco
    verificacao: str


@dataclass(frozen=True)
class ContratoAplicacao:
    id: str
    nome: str
    versao: str
    descricao: str
    fornecedor: str
    autor: str
    tipo: str
    pasta: Path
    entrada: Path | None
    health_url: str | None
    recursos: dict[str, Any]
    operacoes: tuple[OperacaoAplicacao, ...]


def ler_contrato(manifesto: Path) -> ContratoAplicacao:
    manifesto = Path(manifesto).resolve()
    dados = json.loads(manifesto.read_text(encoding="utf-8-sig"))
    if not isinstance(dados, dict) or dados.get("schemaVersion") != 2:
        raise ValueError("Manifesto precisa usar schemaVersion 2")
    identificador = dados.get("id")
    if not isinstance(identificador, str) or not IDENTIFICADOR.fullmatch(identificador):
        raise ValueError("ID de aplicação inválido")
    nome, versao = dados.get("name"), dados.get("version")
    if not isinstance(nome, str) or not nome.strip() or not isinstance(versao, str) or not versao.strip():
        raise ValueError("Nome e versão são obrigatórios")
    tipo = dados.get("kind")
    if tipo not in {"static-web", "web-service", "remote-web", "desktop", "planned"}:
        raise ValueError("Tipo de aplicação inválido")
    pasta = manifesto.parent
    entrada = None
    if dados.get("entryFile") is not None:
        if not isinstance(dados["entryFile"], str) or not dados["entryFile"].strip():
            raise ValueError("Arquivo de entrada inválido")
        entrada = (pasta / dados["entryFile"]).resolve()
        if not entrada.is_relative_to(pasta):
            raise ValueError("Arquivo de entrada fora da aplicação")
    recursos = dados.get("capabilities", {})
    if not isinstance(recursos, dict):
        raise ValueError("Recursos inválidos")
    declaradas = dados.get("agentOperations", [])
    if not isinstance(declaradas, list):
        raise ValueError("agentOperations deve ser uma lista")
    operacoes = []
    nomes = set()
    for item in declaradas:
        if not isinstance(item, dict):
            raise ValueError("Operação inválida")
        nome_operacao = item.get("name")
        parametros = item.get("parameters", [])
        descricao = item.get("description")
        verificacao = item.get("verification")
        if (not isinstance(nome_operacao, str) or not NOME_FERRAMENTA.fullmatch(nome_operacao)
                or nome_operacao in nomes or not isinstance(descricao, str) or not descricao.strip()
                or not isinstance(parametros, list) or not all(isinstance(p, str) and p.isidentifier() for p in parametros)
                or len(set(parametros)) != len(parametros) or not isinstance(verificacao, str)
                or not verificacao.strip()):
            raise ValueError(f"Operação inválida em {identificador}")
        try:
            risco = Risco(item["risk"])
        except (KeyError, ValueError, TypeError) as erro:
            raise ValueError(f"Risco inválido em {nome_operacao}") from erro
        nomes.add(nome_operacao)
        operacoes.append(OperacaoAplicacao(nome_operacao, descricao, tuple(parametros), risco, verificacao))
    fornecedor = dados.get("vendor", FORNECEDOR)
    autor = dados.get("author", FORNECEDOR)
    if fornecedor != FORNECEDOR or autor != FORNECEDOR:
        raise ValueError("Atribuição Ink-guginha ausente ou divergente")
    return ContratoAplicacao(identificador, nome.strip(), versao.strip(),
                            str(dados.get("description", "")), fornecedor, autor, tipo,
                            pasta, entrada, dados.get("healthUrl"), recursos,
                            tuple(operacoes))
