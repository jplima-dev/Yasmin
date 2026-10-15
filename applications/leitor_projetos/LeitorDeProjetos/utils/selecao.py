"""Estado editável da prévia, sem ler conteúdo nem alterar preferências salvas."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from utils.arquivos import FiltroIgnorados, eh_arquivo_sensivel


@dataclass(frozen=True)
class ItemPrevia:
    caminho: str
    pasta: bool
    estado: str


class SelecaoProjeto:
    def __init__(self, raiz, extensoes, pastas_ignoradas, arquivos_ignorados, selecionados=None):
        self.raiz = Path(raiz).resolve()
        self.extensoes = tuple(extensoes)
        self.pastas_ignoradas = list(pastas_ignoradas)
        self.arquivos_ignorados = list(arquivos_ignorados)
        self.selecionados = None if selecionados is None else {
            os.path.normcase(os.path.abspath(p)) for p in selecionados}
        self.itens: dict[str, ItemPrevia] = {}
        self.erros: list[str] = []
        self.atualizar()

    def _chave(self, relativo):
        return os.path.normcase(os.path.abspath(self.raiz / relativo))

    @staticmethod
    def _dentro(caminho, pasta):
        return caminho == pasta or caminho.startswith(pasta + "/")

    def atualizar(self):
        self.itens = {}
        self.erros = []
        pastas = FiltroIgnorados(self.pastas_ignoradas, str(self.raiz))
        arquivos = FiltroIgnorados(self.arquivos_ignorados, str(self.raiz))
        for diretorio, dirs, nomes in os.walk(self.raiz, onerror=lambda erro: self.erros.append(str(erro))):
            # Mostra pastas ignoradas, mas não percorre seus descendentes.
            # Evita carregar dependências e caches enormes só para a prévia.
            for nome in sorted(dirs):
                caminho = Path(diretorio, nome)
                relativo = caminho.relative_to(self.raiz).as_posix()
                bloqueado = caminho.is_symlink() or (caminho / ".leitor-ia").exists()
                estado = "previa_bloqueado" if bloqueado else (
                    "previa_ignorado" if pastas.corresponde(caminho) else "previa_pasta")
                self.itens[relativo] = ItemPrevia(relativo, True, estado)
            dirs[:] = sorted(d for d in dirs if self.itens[
                Path(diretorio, d).relative_to(self.raiz).as_posix()].estado == "previa_pasta")
            for nome in sorted(nomes):
                caminho = Path(diretorio, nome)
                relativo = caminho.relative_to(self.raiz).as_posix()
                if eh_arquivo_sensivel(nome) or caminho.is_symlink() or not nome.endswith(self.extensoes):
                    estado = "previa_bloqueado"
                elif arquivos.corresponde(caminho):
                    estado = "previa_ignorado"
                elif self.selecionados is not None and self._chave(relativo) not in self.selecionados:
                    estado = "previa_nao_selecionado"
                else:
                    estado = "previa_incluido"
                self.itens[relativo] = ItemPrevia(relativo, False, estado)

    def ignorar(self, caminhos):
        itens = [self.itens[p] for p in caminhos if p in self.itens
                 and self.itens[p].estado != "previa_bloqueado"]
        for item in itens:
            # Selecionar pai e filho ao mesmo tempo gera apenas a regra do pai.
            if any(p.pasta and p.caminho != item.caminho and self._dentro(item.caminho, p.caminho)
                   for p in itens):
                continue
            regras = self.pastas_ignoradas if item.pasta else self.arquivos_ignorados
            if not FiltroIgnorados(regras, str(self.raiz)).corresponde(self.raiz / item.caminho):
                regras.append("./" + item.caminho)
        self.atualizar()

    def incluir(self, caminhos):
        itens = [self.itens[p] for p in caminhos if p in self.itens
                 and self.itens[p].estado != "previa_bloqueado"]
        for item in itens:
            regras = self.pastas_ignoradas if item.pasta else self.arquivos_ignorados
            regras[:] = [regra for regra in regras if not FiltroIgnorados(
                [regra], str(self.raiz)).corresponde(self.raiz / item.caminho)]
        self.atualizar()
        if self.selecionados is not None:
            for caminho, item in self.itens.items():
                if not item.pasta and item.estado in ("previa_incluido", "previa_nao_selecionado"):
                    if any(caminho == alvo.caminho or alvo.pasta and self._dentro(caminho, alvo.caminho)
                           for alvo in itens):
                        self.selecionados.add(self._chave(caminho))
            self.atualizar()

    def resultado(self):
        incluidos, ignorados = [], []
        for caminho, item in self.itens.items():
            if not item.pasta:
                destino = incluidos if item.estado == "previa_incluido" else ignorados
                destino.append(str(self.raiz / caminho))
        return incluidos, ignorados
