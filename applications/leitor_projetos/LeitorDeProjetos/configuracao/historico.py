"""
Histórico de processamentos realizados.

Armazena apenas metadados (data, nome do projeto, quantidade de
arquivos, modo, pasta de resultado) — nunca o conteúdo dos arquivos
processados, conforme exigido na especificação.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from configuracao.config import obter_diretorio_config

MAX_ENTRADAS = 50


@dataclass
class EntradaHistorico:
    data: str  # formato dd/mm/aaaa HH:MM
    nome_projeto: str
    quantidade_arquivos: int
    modo: str  # "separado" | "junto"
    pasta_resultado: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def obter_caminho_historico() -> Path:
    return obter_diretorio_config() / "historico.json"


def carregar_historico() -> list[EntradaHistorico]:
    caminho = obter_caminho_historico()
    if not caminho.exists():
        return []

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if not isinstance(dados, list):
            return []
        return [EntradaHistorico(**item) for item in dados]
    except (json.JSONDecodeError, OSError, TypeError):
        return []


def adicionar_entrada(
    nome_projeto: str,
    quantidade_arquivos: int,
    modo: str,
    pasta_resultado: str,
) -> None:
    historico = carregar_historico()

    nova = EntradaHistorico(
        data=datetime.now().strftime("%d/%m/%Y %H:%M"),
        nome_projeto=nome_projeto,
        quantidade_arquivos=quantidade_arquivos,
        modo=modo,
        pasta_resultado=pasta_resultado,
    )

    historico.insert(0, nova)
    historico = historico[:MAX_ENTRADAS]

    caminho = obter_caminho_historico()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump([e.to_dict() for e in historico], f, ensure_ascii=False, indent=2)


def limpar_historico() -> None:
    caminho = obter_caminho_historico()
    if caminho.exists():
        caminho.unlink()
