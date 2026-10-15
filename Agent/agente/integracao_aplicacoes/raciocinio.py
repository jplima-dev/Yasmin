"""Reconhece pedidos de abertura por nomes declarados, sem conhecer suas implementações."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from agente.modelos import Objetivo
from agente.raciocinio import MecanismoRaciocinio

from .descoberta import descobrir_aplicacoes


def _normalizar(texto: str) -> str:
    decomposicao = unicodedata.normalize("NFKD", texto.casefold())
    return re.sub(r"\s+", " ", "".join(c for c in decomposicao if not unicodedata.combining(c))).strip()


class RaciocinioAplicacoes:
    def __init__(self, base: MecanismoRaciocinio, raiz: Path):
        self.base = base
        self.raiz = Path(raiz)

    def identificar(self, texto: str) -> Objetivo | None:
        normal = _normalizar(texto)
        if re.search(r"\b(?:nao|nunca|jamais)\b.{0,60}\b(?:liste|listar|mostre|abra|abre|abrir|inicie|iniciar|prepare|organize|deixe|ajude)\b", normal):
            return None
        consulta = re.match(
            r"(?:(?:yasmin|yasm|yas),?\s+)?(?:liste|listar|mostre)\s+"
            r"(?:os\s+)?arquivos\s+d[oa]\s+projeto\s+(.+)$",
            texto.strip(), re.IGNORECASE,
        )
        if consulta:
            caminho = consulta.group(1).strip().strip('"\'“”')
            return Objetivo(texto, parametros={"tipo": "listar_arquivos_projeto_ink",
                                              "caminho": caminho,
                                              "perceptor": "aplicacao:project-reader"})
        if re.search(r"\b(?:liste|listar|mostre)\b.*\bcadernos\b", normal):
            return Objetivo(texto, parametros={"tipo": "listar_cadernos_ink",
                                              "perceptor": "aplicacao:notebook"})
        pedido = re.fullmatch(
            r"(?:(?:yasmin|yasm|yas),?\s+)?(?:abra|abre|abrir|inicie|iniciar|mostre)\s+"
            r"(?:(?:o|a|um|uma)\s+)?(?:(?:aplicativo|aplicacao|app|projeto)\s+)?(.+?)[.!?]?",
            normal,
        )
        verbo = re.search(r"\b(?:abra|abre|abrir|inicie|iniciar|mostre)\b", normal)
        if verbo and not re.search(r"\b(?:nao|nunca|jamais|sem|como)\b", normal[:verbo.start()]):
            alvo = (pedido.group(1) if pedido else normal[verbo.end():]).strip().strip('"\'“”')
            alvo = re.sub(r"^(?:(?:por favor|pra mim|para mim)\s+)*(?:(?:o|a|um|uma)\s+)?(?:(?:aplicativo|aplicacao|app|projeto)\s+)?", "", alvo).strip()
            descoberta = descobrir_aplicacoes(self.raiz)
            correspondencias = []
            for app in descoberta.aplicacoes:
                apelidos = {_normalizar(app.id), _normalizar(app.nome), _normalizar(app.pasta.name)}
                if app.id == "workspace-os":
                    apelidos.update({"workspace", "workspace os", "ink workspace"})
                if any(alvo == apelido or re.match(rf"^{re.escape(apelido)}\b(?:\s+(?:por favor|pra mim|para mim|para|que))\b", alvo)
                       for apelido in apelidos if apelido):
                    correspondencias.append(app)
            if len(correspondencias) == 1:
                app = correspondencias[0]
                return Objetivo(texto, tipo="comando", parametros={
                    "tipo": "abrir_aplicacao_ink", "aplicacao": app.id,
                    "perceptor": f"aplicacao:{app.id}",
                })
        return self.base.identificar(texto)
