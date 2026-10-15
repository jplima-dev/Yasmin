from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .modelos import ResultadoFerramenta, Risco


@dataclass(frozen=True)
class Ferramenta:
    nome: str
    descricao: str
    parametros: tuple[str, ...]
    risco: Risco
    executar: Callable[..., ResultadoFerramenta]
    verificacao: str | None = None


class RegistroFerramentas:
    def __init__(self):
        self._ferramentas: dict[str, Ferramenta] = {}

    def registrar(self, ferramenta: Ferramenta) -> None:
        if ferramenta.nome in self._ferramentas:
            raise ValueError(f"Ferramenta duplicada: {ferramenta.nome}")
        self._ferramentas[ferramenta.nome] = ferramenta

    def obter(self, nome: str) -> Ferramenta:
        return self._ferramentas[nome]

    def listar(self) -> tuple[Ferramenta, ...]:
        return tuple(self._ferramentas.values())


class Executor:
    def __init__(self, registro: RegistroFerramentas):
        self.registro = registro

    def executar(self, nome: str, parametros: dict[str, Any], confirmado: bool = False) -> ResultadoFerramenta:
        try:
            ferramenta = self.registro.obter(nome)
        except KeyError:
            return ResultadoFerramenta(False, erro=f"Ferramenta indisponível: {nome}")
        if ferramenta.risco == Risco.ALTO and not confirmado:
            return ResultadoFerramenta(False, erro="Confirmação explícita necessária")
        ausentes = set(ferramenta.parametros) - set(parametros)
        if ausentes:
            return ResultadoFerramenta(False, erro=f"Parâmetros ausentes: {', '.join(sorted(ausentes))}")
        try:
            resultado = ferramenta.executar(**parametros)
            if not isinstance(resultado, ResultadoFerramenta):
                return ResultadoFerramenta(False, erro="Ferramenta retornou resultado inválido")
            return resultado
        except Exception as erro:
            return ResultadoFerramenta(False, erro=f"{type(erro).__name__}: {erro}")
