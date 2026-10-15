from __future__ import annotations

from collections.abc import Callable

from .modelos import Etapa, Observacao, ResultadoVerificacao, StatusVerificacao


class Verificador:
    def __init__(self):
        self._verificadores: dict[str, Callable[[Etapa, Observacao], ResultadoVerificacao]] = {}

    def registrar(self, nome: str, funcao: Callable[[Etapa, Observacao], ResultadoVerificacao]) -> None:
        self._verificadores[nome] = funcao

    def verificar(self, etapa: Etapa, observacao: Observacao) -> ResultadoVerificacao:
        if etapa.verificacao not in self._verificadores:
            return ResultadoVerificacao(StatusVerificacao.INCERTO, 0.0, ("Sem verificador ambiental",))
        return self._verificadores[etapa.verificacao](etapa, observacao)
