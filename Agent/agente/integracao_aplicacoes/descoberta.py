"""Descoberta isolada dos projetos presentes em applications/."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .contrato import ContratoAplicacao, FORNECEDOR, ler_contrato


@dataclass(frozen=True)
class DescobertaAplicacoes:
    aplicacoes: tuple[ContratoAplicacao, ...]
    erros: tuple[str, ...]


def descobrir_aplicacoes(raiz: Path) -> DescobertaAplicacoes:
    raiz = Path(raiz).resolve()
    encontradas = []
    erros = []
    ids = set()
    if not raiz.is_dir():
        return DescobertaAplicacoes((), (f"Diretório de aplicações ausente: {raiz}",))
    for pasta in sorted(raiz.iterdir()):
        if not pasta.is_dir():
            continue
        manifesto = pasta / "ink-module.json"
        if manifesto.is_file():
            try:
                contrato = ler_contrato(manifesto)
                if contrato.id in ids:
                    raise ValueError(f"ID duplicado: {contrato.id}")
                ids.add(contrato.id)
                encontradas.append(contrato)
            except (OSError, ValueError) as erro:
                erros.append(f"{manifesto}: {type(erro).__name__}: {erro}")
        elif pasta.name == "workspace-os":
            try:
                projeto = tomllib.loads((pasta / "pyproject.toml").read_text(encoding="utf-8"))["project"]
                encontradas.append(ContratoAplicacao(
                    "workspace-os", "Workspace OS", str(projeto["version"]),
                    str(projeto.get("description", "")), FORNECEDOR, FORNECEDOR,
                    "web-service", pasta, None, "http://127.0.0.1:8790/api/health",
                    {"infraestrutura": True}, (),
                ))
            except (OSError, ValueError, KeyError, TypeError) as erro:
                erros.append(f"{pasta}: {type(erro).__name__}: {erro}")
    return DescobertaAplicacoes(tuple(encontradas), tuple(erros))
