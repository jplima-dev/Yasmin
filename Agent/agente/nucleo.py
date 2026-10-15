from __future__ import annotations

import logging
import re
import threading
from typing import Protocol

from .ferramentas import Executor, RegistroFerramentas
from .modelos import (EstadoAgente, Objetivo, ResultadoAgente, ResultadoVerificacao, StatusAgente,
                      StatusEtapa, StatusVerificacao)
from .percepcao import Percepcao
from .planejamento import Planejador
from .raciocinio import MecanismoRaciocinio
from .verificacao import Verificador
from .decisao import DecisorInteracao, normalizar

log = logging.getLogger("yasm.agente")


class ServicoMemoria(Protocol):
    def recuperar(self, objetivo: Objetivo, limite: int = 8) -> list[dict]: ...
    def registrar_experiencia(self, objetivo: Objetivo, aplicativo: str) -> None: ...
    def registrar_objetivo(self, objetivo: Objetivo, status: str) -> None: ...


class NucleoAgente:
    def __init__(self, percepcao: Percepcao, memoria: ServicoMemoria,
                 raciocinio: MecanismoRaciocinio, planejador: Planejador,
                 ferramentas: RegistroFerramentas, verificador: Verificador,
                 limite_acoes: int = 12):
        self.percepcao = percepcao
        self.memoria = memoria
        self.raciocinio = raciocinio
        self.planejador = planejador
        self.executor = Executor(ferramentas)
        self.verificador = verificador
        self.limite_acoes = limite_acoes
        self.estado = EstadoAgente()
        self._cancelado = threading.Event()
        self._pendente_confirmacao: Objetivo | None = None

    def _progresso(self, descricao: str, status: str) -> None:
        """Mantém apenas eventos operacionais curtos para a interface local."""
        self.estado.processos.append({"descricao": descricao, "status": status})
        del self.estado.processos[:-8]

    def atender(self, texto: str, conversacao_factory, intencao_legada: tuple | None = None,
                motor_decisao=None, historico: list[dict] | None = None,
                confirmacao_pendente: bool = False) -> str | None:
        """Decide entre resposta, esclarecimento, plano verificado e capacidade legada.

        None indica uma operação legada reconhecida, preservada pelo adaptador de entrada.
        """
        self.estado.processos.clear()
        self.estado.ultima_observacao = self.percepcao.entrada(texto)
        self.estado.status = StatusAgente.INTERPRETANDO
        self.estado.tarefa_atual = "Interpretando pedido"
        self._progresso("Interpretando pedido", "executando")
        if self._pendente_confirmacao is not None:
            resposta = re.sub(r"^(?:yasmin|yasm|yas)[,\s]+", "", normalizar(texto)).strip(" .!?")
            if resposta in {"sim", "confirmo", "pode fechar", "pode executar"}:
                objetivo = self._pendente_confirmacao
                self._pendente_confirmacao = None
                return self.executar(objetivo.descricao, objetivo, confirmado=True).mensagem
            self._pendente_confirmacao = None
            if resposta in {"nao", "cancela", "cancelar", "deixa pra la"}:
                self.estado.status = StatusAgente.CANCELADO
                return "Cancelei a operação."
        decisao = DecisorInteracao(self.raciocinio, motor_decisao,
                                  self.executor.registro).decidir(
            texto, historico, intencao_legada, confirmacao_pendente)
        self.estado.contexto_imediato["via"] = decisao.via
        self.estado.contexto_imediato["origem_decisao"] = decisao.origem
        log.debug("[AGENTE] Decisão: %s (%s)", decisao.via, decisao.origem)
        if decisao.via == "objetivo":
            resultado = self.executar(texto, decisao.objetivo)
            resultado.estado.contexto_imediato["via"] = decisao.via
            resultado.estado.contexto_imediato["origem_decisao"] = decisao.origem
            return resultado.mensagem
        if decisao.via == "esclarecer":
            self.estado.status = StatusAgente.BLOQUEADO
            self._progresso("Aguardando esclarecimento", "bloqueado")
            return decisao.mensagem
        if decisao.via == "conversa":
            self.estado.status = StatusAgente.RESPONDENDO
            self.estado.tarefa_atual = "Preparando resposta"
            self._progresso("Preparando resposta", "executando")
            resposta = self.conversar(texto, conversacao_factory())
            self.estado.status = StatusAgente.CONCLUIDO
            self._progresso("Resposta concluída", "concluido")
            return resposta
        return None

    def concluir_legado(self, resposta: str | None) -> None:
        """Fecha o estado da via de compatibilidade após o adaptador responder."""
        if (self.estado.contexto_imediato.get("via") == "legado"
                and self.estado.status == StatusAgente.INTERPRETANDO):
            self.estado.status = StatusAgente.CONCLUIDO if resposta else StatusAgente.BLOQUEADO
            self._progresso("Comando concluído" if resposta else "Comando sem resposta",
                           self.estado.status.value)

    def _resposta(self, status: StatusAgente, mensagem: str) -> ResultadoAgente:
        self.estado.status = status
        if status in {StatusAgente.CONCLUIDO, StatusAgente.FALHOU,
                      StatusAgente.BLOQUEADO, StatusAgente.CANCELADO}:
            self._progresso("Objetivo " + status.value, status.value)
        objetivo = self.estado.objetivo_atual
        if objetivo is not None:
            try:
                self.memoria.registrar_objetivo(objetivo, status.value)
            except Exception as erro:
                log.debug("[AGENTE] Status do objetivo não persistido: %s", erro)
        return ResultadoAgente(status, mensagem, self.estado)

    def executar(self, texto: str, objetivo: Objetivo | None = None,
                 confirmado: bool = False) -> ResultadoAgente:
        self._cancelado.clear()
        estado = self.estado = EstadoAgente()
        estado.ultima_observacao = self.percepcao.entrada(texto)
        estado.tarefa_atual = "Observando pedido"
        self._progresso("Pedido recebido", "concluido")
        log.debug("[AGENTE] Entrada percebida")
        objetivo = objetivo or self.raciocinio.identificar(texto)
        if objetivo is None:
            return self._resposta(StatusAgente.BLOQUEADO, "Ainda não consigo planejar esse objetivo.")
        estado.objetivo_atual = objetivo
        log.debug("[AGENTE] Objetivo recebido: %s", objetivo.descricao)
        perceptor = objetivo.parametros.get("perceptor")
        if isinstance(perceptor, str):
            try:
                observacao = self.percepcao.observar(perceptor)
                estado.ultima_observacao = observacao
                estado.contexto_imediato["estado_aplicacao"] = observacao.dados
            except (KeyError, OSError, ValueError) as erro:
                log.debug("[AGENTE] Percepção indisponível: %s", erro)
        try:
            estado.tarefa_atual = "Recuperando memória relevante"
            self._progresso("Recuperando memória relevante", "executando")
            memorias = self.memoria.recuperar(objetivo)
            estado.contexto_imediato["memorias_recuperadas"] = len(memorias)
            self._progresso("Memória consultada", "concluido")
            log.debug("[AGENTE] Memória relevante recuperada: %s", len(memorias))
            estado.tarefa_atual = "Criando plano"
            self._progresso("Criando plano", "executando")
            estado.plano_atual = self.planejador.criar(objetivo, memorias)
            self._progresso(f"Plano com {len(estado.plano_atual.etapas)} etapas", "concluido")
            log.debug("[AGENTE] Plano criado: %s etapas", len(estado.plano_atual.etapas))
        except Exception as erro:
            estado.erro_atual = str(erro)
            return self._resposta(StatusAgente.BLOQUEADO, f"Não consegui preparar o plano: {erro}")

        for _ in range(self.limite_acoes):
            if self._cancelado.is_set():
                self.planejador.cancelar(estado.plano_atual)
                return self._resposta(StatusAgente.CANCELADO, "Objetivo cancelado.")
            etapa = estado.plano_atual.proxima()
            if etapa is None:
                if any(e.status in (StatusEtapa.PENDENTE, StatusEtapa.EXECUTANDO) for e in estado.plano_atual.etapas):
                    return self._resposta(StatusAgente.BLOQUEADO, "O plano tem dependências pendentes.")
                estado.status = StatusAgente.CONCLUIDO
                aplicativo = next((e.parametros["nome"] for e in reversed(estado.plano_atual.etapas)
                                   if e.ferramenta == "abrir_aplicativo" and e.status == StatusEtapa.CONCLUIDA), None)
                if aplicativo:
                    try:
                        self.memoria.registrar_experiencia(objetivo, aplicativo)
                    except Exception as erro:
                        log.debug("[AGENTE] Experiência não persistida: %s", erro)
                log.debug("[AGENTE] Objetivo concluído")
                if aplicativo:
                    mensagem = (f"Abri {aplicativo}." if objetivo.tipo == "comando" else
                                f"Ambiente preparado: {aplicativo}.")
                elif estado.plano_atual.etapas and estado.plano_atual.etapas[-1].ferramenta == "fechar_aplicativo":
                    mensagem = f"Fechei {estado.plano_atual.etapas[-1].parametros['nome']}."
                else:
                    dados_finais = estado.ultimo_resultado.resultado if estado.ultimo_resultado else None
                    mensagem = (dados_finais or {}).get("mensagem") or "Concluído."
                return self._resposta(StatusAgente.CONCLUIDO, mensagem)

            try:
                ferramenta = self.executor.registro.obter(etapa.ferramenta)
            except KeyError:
                etapa.status = StatusEtapa.FALHOU
                estado.etapa_atual = etapa
                estado.erro_atual = f"Ferramenta indisponível: {etapa.ferramenta}"
                return self._resposta(StatusAgente.FALHOU, estado.erro_atual)
            if ferramenta.risco.value == "alto" and not confirmado:
                self._pendente_confirmacao = objetivo
                return self._resposta(StatusAgente.CONFIRMACAO, f"Confirmação necessária para {etapa.descricao}.")
            etapa.status = StatusEtapa.EXECUTANDO
            etapa.tentativas += 1
            estado.etapa_atual = etapa
            estado.tarefa_atual = etapa.descricao
            estado.ferramenta_atual = etapa.ferramenta
            estado.acao_atual = etapa.descricao
            estado.status = StatusAgente.EXECUTANDO
            self._progresso(etapa.descricao, "executando")
            log.debug("[AGENTE] Etapa iniciada: %s", etapa.descricao)
            resultado = self.executor.executar(etapa.ferramenta, etapa.parametros, confirmado)
            etapa.resultado = resultado
            estado.ultimo_resultado = resultado
            observacao = self.percepcao.resultado(etapa.ferramenta, resultado.sucesso,
                                                 resultado.resultado or {}, resultado.erro)
            estado.ultima_observacao = observacao
            try:
                evidencia = self.verificador.verificar(etapa, observacao)
                if not isinstance(evidencia, ResultadoVerificacao):
                    raise TypeError("Verificador retornou resultado inválido")
            except Exception as erro:
                log.debug("[VERIFICADOR] Falha ao verificar %s", etapa.descricao, exc_info=True)
                evidencia = ResultadoVerificacao(StatusVerificacao.INCERTO, 0.0,
                                                  (f"Falha na verificação: {type(erro).__name__}",))
            etapa.evidencia = evidencia
            estado.ultima_acao = estado.acao_atual
            estado.acao_atual = None
            log.debug("[VERIFICADOR] %s: %s", etapa.descricao, evidencia.status.value)
            if evidencia.status == StatusVerificacao.SUCESSO:
                etapa.status = StatusEtapa.CONCLUIDA
                self._progresso(etapa.descricao, "concluido")
                if etapa.ferramenta in {"abrir_aplicativo", "abrir_aplicacao_ink"}:
                    estado.aplicativo_ativo = etapa.parametros.get("nome") or etapa.parametros.get("aplicacao")
                continue
            if evidencia.status == StatusVerificacao.INCERTO:
                etapa.status = StatusEtapa.INCERTA
                self._progresso(etapa.descricao, "incerto")
                estado.erro_atual = "; ".join(evidencia.evidencias)
                return self._resposta(StatusAgente.BLOQUEADO, f"Não consegui confirmar {etapa.descricao.lower()}.")
            etapa.status = StatusEtapa.FALHOU
            self._progresso(etapa.descricao, "falhou")
            estado.erro_atual = resultado.erro or "; ".join(evidencia.evidencias)
            if self.planejador.replanejar(estado.plano_atual, etapa, objetivo):
                self._progresso("Replanejando após falha", "executando")
                log.debug("[AGENTE] Plano revisado após falha: %s", estado.erro_atual)
                continue
            return self._resposta(StatusAgente.FALHOU, f"Não consegui {etapa.descricao.lower()}: {estado.erro_atual}")
        return self._resposta(StatusAgente.BLOQUEADO, "Limite de ações atingido.")

    def cancelar(self) -> None:
        self._cancelado.set()
        self._pendente_confirmacao = None
        if self.estado.plano_atual:
            self.planejador.cancelar(self.estado.plano_atual)
        self.estado.status = StatusAgente.CANCELADO

    def conversar(self, texto: str, servico) -> str:
        """Percebe uma fala conversacional usando o mesmo estado e a mesma memória."""
        self.estado.ultima_observacao = self.percepcao.entrada(texto)
        self.estado.status = StatusAgente.RESPONDENDO
        try:
            resposta = servico.responder(texto)
        except Exception:
            self.estado.status = StatusAgente.FALHOU
            raise
        self.estado.status = StatusAgente.CONCLUIDO
        return resposta
