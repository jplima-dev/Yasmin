from __future__ import annotations

from collections.abc import Callable
from .modelos import Observacao


class Percepcao:
    def __init__(self):
        self._perceptores: dict[str, Callable[[], Observacao]] = {}

    def registrar(self, nome: str, perceptor: Callable[[], Observacao]) -> None:
        if nome in self._perceptores:
            raise ValueError(f"Perceptor duplicado: {nome}")
        self._perceptores[nome] = perceptor

    def entrada(self, texto: str, fonte: str = "usuario") -> Observacao:
        return Observacao("entrada", fonte, {"texto": texto})

    def observar(self, nome: str) -> Observacao:
        return self._perceptores[nome]()

    def resultado(self, ferramenta: str, sucesso: bool, dados: dict, erro: str | None) -> Observacao:
        return Observacao("resultado_ferramenta", ferramenta,
                          {"sucesso": sucesso, "resultado": dados, "erro": erro})
