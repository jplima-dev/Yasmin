from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def agora() -> datetime:
    return datetime.now(timezone.utc)


class StatusEtapa(str, Enum):
    PENDENTE = "pendente"
    EXECUTANDO = "executando"
    CONCLUIDA = "concluida"
    FALHOU = "falhou"
    INCERTA = "incerta"
    CANCELADA = "cancelada"
    IGNORADA = "ignorada"


class StatusAgente(str, Enum):
    INTERPRETANDO = "interpretando"
    RESPONDENDO = "respondendo"
    PLANEJANDO = "planejando"
    EXECUTANDO = "executando"
    CONCLUIDO = "concluido"
    FALHOU = "falhou"
    BLOQUEADO = "bloqueado"
    CONFIRMACAO = "confirmacao"
    CANCELADO = "cancelado"


class StatusVerificacao(str, Enum):
    SUCESSO = "sucesso"
    FALHA = "falha"
    INCERTO = "incerto"


class Risco(str, Enum):
    BAIXO = "baixo"
    MEDIO = "medio"
    ALTO = "alto"


@dataclass(frozen=True)
class Observacao:
    tipo: str
    fonte: str
    dados: dict[str, Any]
    confianca: float = 1.0
    timestamp: datetime = field(default_factory=agora)


@dataclass(frozen=True)
class Objetivo:
    descricao: str
    tipo: str = "objetivo"
    parametros: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))


@dataclass
class Etapa:
    descricao: str
    ferramenta: str
    parametros: dict[str, Any] = field(default_factory=dict)
    dependencias: tuple[str, ...] = ()
    verificacao: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    status: StatusEtapa = StatusEtapa.PENDENTE
    tentativas: int = 0
    resultado: ResultadoFerramenta | None = None
    evidencia: ResultadoVerificacao | None = None


@dataclass
class Plano:
    etapas: list[Etapa]
    revisao: int = 0
    id: str = field(default_factory=lambda: str(uuid4()))

    def proxima(self) -> Etapa | None:
        concluidas = {e.id for e in self.etapas if e.status == StatusEtapa.CONCLUIDA}
        return next((e for e in self.etapas if e.status == StatusEtapa.PENDENTE
                     and set(e.dependencias) <= concluidas), None)


@dataclass(frozen=True)
class ResultadoFerramenta:
    sucesso: bool
    resultado: dict[str, Any] | None = None
    erro: str | None = None


@dataclass(frozen=True)
class ResultadoVerificacao:
    status: StatusVerificacao
    confianca: float
    evidencias: tuple[str, ...] = ()


@dataclass
class EstadoAgente:
    objetivo_atual: Objetivo | None = None
    tarefa_atual: str | None = None
    plano_atual: Plano | None = None
    etapa_atual: Etapa | None = None
    ferramenta_atual: str | None = None
    acao_atual: str | None = None
    ultima_acao: str | None = None
    ultimo_resultado: ResultadoFerramenta | None = None
    ultima_observacao: Observacao | None = None
    erro_atual: str | None = None
    aplicativo_ativo: str | None = None
    contexto_imediato: dict[str, Any] = field(default_factory=dict)
    processos: list[dict[str, str]] = field(default_factory=list)
    status: StatusAgente = StatusAgente.PLANEJANDO


@dataclass(frozen=True)
class ResultadoAgente:
    status: StatusAgente
    mensagem: str
    estado: EstadoAgente
