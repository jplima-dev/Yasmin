"""Escolha da próxima via de atendimento, sem acesso a provedores ou ferramentas concretas."""

from __future__ import annotations

import re
import unicodedata
import logging
from dataclasses import dataclass
from typing import Protocol

from .modelos import Objetivo
from .raciocinio import MecanismoRaciocinio
from .ferramentas import RegistroFerramentas
from .planos_ferramentas import catalogo_planejavel, objetivo_de_proposta
from .composicao_local import compor_projeto

log = logging.getLogger("yasm.agente")


def normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto).casefold())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", base).strip()


@dataclass(frozen=True)
class Decisao:
    via: str  # objetivo, conversa, legado ou esclarecer
    objetivo: Objetivo | None = None
    mensagem: str | None = None
    origem: str = "local"


class MotorDecisao(Protocol):
    def classificar(self, texto: str, historico: list[dict[str, str]],
                   operacoes: dict[str, dict]) -> dict | None: ...


class DecisorInteracao:
    """Usa regras para certezas locais e modelo opcional somente em pedidos ambíguos."""

    _legado = {"HORA", "DATA", "ENCERRAR", "ABRIR_APLICATIVO", "FECHAR_APLICATIVO",
               "ATALHO_JAVA", "ATALHO_PROGRAMAR", "ATALHO_BANCO", "MUSICA", "MEMORIA",
               "TAREFAS", "TIMER", "VOLUME", "PESQUISA", "ESTUDO", "CALCULO", "SITE", "QUIZ_PENDENTE"}
    _operacoes_semanticas = {
        "preparar_programacao": {"descricao": "Preparar o ambiente para programar",
                                 "linguagem": ["java", "geral"]},
        "listar_aplicacoes_ink": {"descricao": "Listar aplicações Ink-guginha disponíveis"},
    }

    def __init__(self, raciocinio: MecanismoRaciocinio, motor: MotorDecisao | None = None,
                 ferramentas: RegistroFerramentas | None = None):
        self.raciocinio = raciocinio
        self.motor = motor
        self.ferramentas = ferramentas

    def _propor_plano(self, texto: str) -> Decisao | None:
        if self.motor is None or self.ferramentas is None:
            return None
        proponente = getattr(self.motor, "propor_plano", None)
        if not callable(proponente):
            return None
        try:
            proposta = proponente(texto[:1000], catalogo_planejavel(self.ferramentas))
            objetivo = objetivo_de_proposta(texto, proposta, self.ferramentas)
        except Exception as erro:
            log.debug("[AGENTE] Proposta de plano indisponível: %s", erro)
            return None
        return Decisao("objetivo", objetivo=objetivo, origem="modelo_validado") if objetivo else None

    def decidir(self, texto: str, historico: list[dict[str, str]] | None = None,
               intencao_legada: tuple[str, bool] | None = None,
               confirmacao_pendente: bool = False) -> Decisao:
        normal = normalizar(texto)
        normal = re.sub(r"^(?:yasmin|yasm|yas)[,\s]+", "", normal)
        if re.search(r"\b(?:nao|nunca|jamais)\b.{0,60}\b(?:abra|abre|abrir|inicie|iniciar|prepare|preparar|organize|configure|deixe|ajude|analise|liste|mostre|feche|fechar|exclua|apague)\b", normal):
            return Decisao("esclarecer", mensagem="Entendi. Não vou executar essa ação.")
        if re.search(r"\b(?:apague|apagar|exclua|excluir|delete|remova|remover|instale|instalar|desinstale)\b", normal):
            return Decisao("esclarecer", mensagem="Esse pedido inclui uma ação que não posso planejar com segurança. Qual resultado concreto devo buscar? Descreva uma tarefa por vez.")
        if re.search(r"\b(?:compile|compilar|publique|publicar|deploy|implante)\b|\b(?:execute|executar|rode|rodar|teste|testar)\s+(?:os?\s+)?(?:testes?|scripts?|comandos?|build|projeto)\b", normal):
            return Decisao("esclarecer", mensagem="Ainda não tenho uma ferramenta verificada para essa execução. Posso analisar o projeto ou preparar a documentação se você indicar o caminho.")
        if re.search(r"\b(?:antes|primeiro)\b.{0,50}\b(?:explique|explica|diga|conte|fale)\b", normal):
            return Decisao("conversa")
        acoes_seguintes = re.findall(
            r"\b(?:e(?: depois)?|em seguida|depois disso)\s+"
            r"(abra|abre|abrir|inicie|iniciar|mostre|liste|prepare|feche|"
            r"gere|gerar|gera|crie|criar|exporte|exportar|leia|ler|analise)\b", normal)
        if acoes_seguintes:
            composto = self.raciocinio.identificar(texto)
            if (composto and composto.parametros.get("tipo") in {
                    "exportar_contexto_projeto_ink", "gerar_readme_projeto",
                    "resumir_projeto_em_arquivo"}
                    and (composto.parametros.get("tipo") == "exportar_contexto_projeto_ink"
                         or not re.search(r"\b(?:abra|abre|abrir|inicie|liste|listar|enumere|mostre)\b", normal))
                    and all(acao in {"gere", "gerar", "gera", "exporte", "exportar", "prepare",
                                       "crie", "criar"} for acao in acoes_seguintes)):
                return Decisao("objetivo", objetivo=composto)
            local = compor_projeto(texto, self.ferramentas) if self.ferramentas else None
            if local:
                return Decisao("objetivo", objetivo=local, origem="composicao_local")
            plano = self._propor_plano(texto)
            if plano:
                return plano
            return Decisao("esclarecer", mensagem="Você pediu mais de uma ação. Diga qual devo executar primeiro.")
        if confirmacao_pendente and normal in {"sim", "nao", "pode", "pode ser", "aceito", "quero", "prefiro nao"}:
            return Decisao("conversa")
        if (normal.startswith(("prefiro ", "fale de forma ", "quero que fale ", "vamos conversar",
                              "o que voce acha", "aprenda ", "guarde na memoria", "quero que voce lembre",
                              "corrija ", "atualize ", "esqueca ", "continua ", "continue "))
                or any(frase in normal for frase in ("como voce prefere as configuracoes",
                       "quais sao suas preferencias", "quais sao minhas preferencias",
                       "me conte uma curiosidade", "nao quero curiosidades", "quero curiosidades"))):
            return Decisao("conversa")
        objetivo = self.raciocinio.identificar(texto)
        if objetivo is not None:
            return Decisao("objetivo", objetivo=objetivo)
        local = compor_projeto(texto, self.ferramentas) if self.ferramentas else None
        if local:
            return Decisao("objetivo", objetivo=local, origem="composicao_local")
        if re.search(r"\b(?:projeto|repositorio|readme|documentacao|arquivos|codigo)\b", normal):
            plano = self._propor_plano(texto)
            if plano:
                return plano
        if re.search(r"\b(?:readme|leitor de projetos|leia? (?:esse |o )?projeto)\b", normal) and re.search(
                r"\b(?:gere|gerar|gera|crie|criar|exporte|exportar|leia|le|ler|resumo)\b", normal):
            return Decisao("esclarecer", mensagem=(
                "Para trabalhar no projeto, informe o caminho completo entre aspas. "
                "Para exportar pelo Leitor, informe também a pasta de destino entre aspas."))
        if intencao_legada and intencao_legada[1] and intencao_legada[0] in {"ABRIR_APLICATIVO", "FECHAR_APLICATIVO"}:
            parametros = intencao_legada[2] if len(intencao_legada) > 2 else {}
            aplicativo = parametros.get("aplicativo") if isinstance(parametros, dict) else None
            if not isinstance(aplicativo, str) or not aplicativo:
                if intencao_legada[0] == "ABRIR_APLICATIVO":
                    return Decisao("legado")
                return Decisao("esclarecer", mensagem="Qual aplicativo você quer fechar?")
            if intencao_legada[0] == "FECHAR_APLICATIVO":
                return Decisao("objetivo", Objetivo(texto, tipo="comando", parametros={
                    "tipo": "fechar_aplicativo", "aplicativo": aplicativo}))
            return Decisao("objetivo", Objetivo(texto, tipo="comando", parametros={"aplicativo": aplicativo}))
        if intencao_legada and intencao_legada[1] and intencao_legada[0] in self._legado:
            return Decisao("legado")
        if intencao_legada and intencao_legada[0] == "MUSICA" and re.search(
                r"\b(?:toque|tocar|coloque|coloca|poe)\b", normal):
            return Decisao("legado")
        if intencao_legada and intencao_legada[0] in {"ABRIR_APLICATIVO", "FECHAR_APLICATIVO"}:
            return Decisao("esclarecer", mensagem="Não tenho certeza do aplicativo. Pode repetir de outra forma?")
        # Uma conversa livre recebe uma só chamada de geração. O classificador
        # semântico é reservado a pedidos de ação que as regras não cobriram.
        parece_acao = re.search(r"\b(?:preciso|ajude|ajuda|organize|prepar[ae]|deixe|configure|abra|abrir|inicie|fa[cz]a|execute|gere|gerar|crie|criar|escreva|documente|leia|analise|exporte|pesquise)\b", normal)
        if not parece_acao and re.search(r"\b(?:quero|gostaria|precisando|ver|listar|liste|mostre|quais)\b", normal):
            parece_acao = re.search(r"\b(?:ambiente|programar|programacao|codar|desenvolvimento|ide|editor|aplicativos|aplicacoes|apps|modulos|ferramentas)\b", normal)
        if parece_acao and self.motor is not None:
            try:
                proposta = self.motor.classificar(texto[:1000], (historico or [])[-4:],
                                                  self._operacoes_semanticas)
            except Exception as erro:
                log.debug("[AGENTE] Classificador semântico falhou: %s", erro)
                proposta = None
            if isinstance(proposta, dict):
                operacao = proposta.get("operacao")
                origem = "modelo_local" if proposta.get("_origem") == "modelo_local" else "modelo_validado"
                if (operacao == "preparar_programacao" and proposta.get("linguagem") in {"java", "geral"}
                        and re.search(r"\b(?:ambiente|programar|programacao|codar|desenvolver|desenvolvimento|ide|editor)\b", normal)):
                    return Decisao("objetivo", Objetivo(texto, parametros={
                        "tipo": operacao, "linguagem": proposta["linguagem"]}), origem=origem)
                if (operacao == "listar_aplicacoes_ink"
                        and re.search(r"\b(?:aplicativos|aplicacoes|apps|modulos|ferramentas)\b", normal)):
                    return Decisao("objetivo", Objetivo(texto, parametros={"tipo": operacao}), origem=origem)
                if proposta.get("via") == "conversa":
                    return Decisao("conversa", origem=origem)
                if proposta.get("via") == "esclarecer":
                    return Decisao("esclarecer", mensagem="Pode dizer qual resultado você espera e qual aplicativo devo usar?",
                                   origem=origem)
        if parece_acao and not normal.endswith("?"):
            return Decisao("esclarecer", mensagem="Entendi que você quer realizar uma tarefa. Qual resultado concreto devo buscar? Digitando o aplicativo ou projeto, consigo planejar com segurança.")
        return Decisao("conversa")
