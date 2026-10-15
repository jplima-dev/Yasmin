# cerebro/cerebro.py

import json
import threading
from copy import deepcopy
from pathlib import Path

from memoria_yasm import salvar_json_atomico

from .contexto import ContextoYasm
from .iniciativa import IniciativaYasm


class CerebroYasm:
    """
    Manager central do cérebro da Yasm.

    Responsável por conectar:
        - contexto.py
        - iniciativa.py
        - memoria.json

    O yas.py conversa apenas com este manager.
    """

    def __init__(
        self,
        arquivo_memoria=None,
        limite_contexto=10,
        chance_pergunta=0.35
    ):
        # ======================================================
        # COMPONENTES
        # ======================================================

        self.contexto = ContextoYasm(
            limite=limite_contexto
        )

        self.iniciativa = IniciativaYasm(
            chance=chance_pergunta
        )

        self.arquivo_memoria = (
            Path(arquivo_memoria) if arquivo_memoria is not None
            else Path(__file__).resolve().with_name("memoria.json")
        )
        self._lock = threading.RLock()

        # Memória permanente
        self.memoria = self._carregar_memoria()

    # ==========================================================
    # MEMÓRIA
    # ==========================================================

    def _memoria_padrao(self):
        """
        Estrutura inicial da memória.
        """

        return {
            "usuario": {},
            "informacoes": {},
            "preferencias": {}
        }

    def _carregar_memoria(self):
        """
        Carrega a memória do JSON.
        """

        try:
            if not self.arquivo_memoria.exists():
                return self._memoria_padrao()

            with open(
                self.arquivo_memoria,
                "r",
                encoding="utf-8"
            ) as arquivo:
                dados = json.load(arquivo)

            if not isinstance(dados, dict):
                return self._memoria_padrao()

            # Garante que as categorias principais existam.
            padrao = self._memoria_padrao()

            for categoria, valores in padrao.items():
                if not isinstance(dados.get(categoria), dict):
                    dados[categoria] = valores

            return dados

        except (ValueError, OSError) as erro:
            print(f"[CÉREBRO] Erro ao carregar memória: {erro}")

            return self._memoria_padrao()

    def _salvar_memoria(self):
        """
        Salva a memória no arquivo JSON.
        """

        with self._lock:
            return salvar_json_atomico(self.arquivo_memoria, self.memoria)

    def lembrar(self, categoria, chave, valor):
        """
        Guarda uma informação permanente.

        Exemplo:
            cerebro.lembrar(
                "usuario",
                "nome",
                "João"
            )
        """

        if not isinstance(categoria, str) or not categoria or not isinstance(chave, str) or not chave:
            return False

        with self._lock:
            anterior = deepcopy(self.memoria)
            if not isinstance(self.memoria.get(categoria), dict):
                self.memoria[categoria] = {}
            self.memoria[categoria][chave] = valor
            if not self._salvar_memoria():
                self.memoria = anterior
                return False
            return True

    def lembrar_usuario(self, chave, valor):
        """
        Atalho para guardar informação do usuário.
        """

        return self.lembrar(
            "usuario",
            chave,
            valor
        )

    def lembrar_preferencia(self, chave, valor):
        """
        Atalho para guardar preferência.
        """

        return self.lembrar(
            "preferencias",
            chave,
            valor
        )

    def lembrar_informacao(self, chave, valor):
        """
        Atalho para guardar informação geral.
        """

        return self.lembrar(
            "informacoes",
            chave,
            valor
        )

    def recordar(self, categoria, chave, padrao=None):
        """
        Recupera uma memória.

        Exemplo:
            nome = cerebro.recordar(
                "usuario",
                "nome"
            )
        """

        with self._lock:
            valores = self.memoria.get(categoria)
            if not isinstance(valores, dict):
                return padrao
            return deepcopy(valores.get(chave, padrao))

    def esquecer(self, categoria, chave):
        """
        Remove uma memória específica.
        """

        with self._lock:
            valores = self.memoria.get(categoria)
            if not isinstance(valores, dict) or chave not in valores:
                return False
            anterior = valores.pop(chave)
            if not self._salvar_memoria():
                valores[chave] = anterior
                return False
            return True

    # ==========================================================
    # CONVERSA / CONTEXTO
    # ==========================================================

    def receber(self, texto_usuario):
        """
        Entrega a fala do usuário ao contexto.

        Retorna os dados atuais da conversa.
        """

        self.contexto.adicionar_usuario(
            texto_usuario
        )

        return {
            "texto": texto_usuario,
            "contexto": self.contexto.resumo(),
            "historico": self.contexto.obter_historico(),
            "assunto": self.contexto.obter_assunto()
        }

    def registrar_resposta(
        self,
        resposta,
        assunto=None
    ):
        """
        Registra uma resposta da Yasm no contexto.
        """

        if assunto:
            self.contexto.definir_assunto(
                assunto
            )

        self.contexto.adicionar_yasm(
            resposta
        )

        return {
            "resposta": resposta,
            "contexto": self.contexto.resumo(),
            "assunto": self.contexto.obter_assunto()
        }

    # ==========================================================
    # INICIATIVA
    # ==========================================================

    def deve_fazer_pergunta(self, resposta):
        """
        Pede ao iniciativa.py para decidir se a Yasm
        deve continuar a conversa.

        A decisão NÃO fica aqui.
        """

        return self.iniciativa.deve_perguntar(
            resposta=resposta
        )

    def tipo_de_pergunta(self, assunto=None):
        """
        Pede ao iniciativa.py um tipo de pergunta.
        """

        return self.iniciativa.escolher_tipo_pergunta(
            assunto
        )

    def registrar_pergunta(self):
        """
        Registra que a Yasm fez uma pergunta espontânea.
        """

        self.iniciativa.registrar_pergunta_iniciativa()

    def registrar_resposta_normal(self):
        """
        Registra que a Yasm respondeu normalmente.
        """

        self.iniciativa.registrar_resposta_normal()

    # ==========================================================
    # PROCESSAMENTO PRINCIPAL
    # ==========================================================

    def processar(
        self,
        texto_usuario,
        resposta_yasm,
        assunto=None
    ):
        """
        MÉTODO PRINCIPAL.

        O yas.py pode usar somente isto:

            resultado = cerebro.processar(
                texto_usuario,
                resposta_yasm
            )

        O manager então conecta:
            contexto.py
            iniciativa.py
            memória
        """

        # ------------------------------------------------------
        # 1. Usuário fala
        # ------------------------------------------------------

        self.contexto.adicionar_usuario(
            texto_usuario
        )

        # ------------------------------------------------------
        # 2. Atualiza assunto
        # ------------------------------------------------------

        if assunto:
            self.contexto.definir_assunto(
                assunto
            )

        # ------------------------------------------------------
        # 3. Yasm responde
        # ------------------------------------------------------

        self.contexto.adicionar_yasm(
            resposta_yasm
        )

        # ------------------------------------------------------
        # 4. Decide se deve fazer pergunta
        # ------------------------------------------------------

        perguntar = self.iniciativa.deve_perguntar(
            texto_usuario=texto_usuario,
            resposta=resposta_yasm,
        )

        # ------------------------------------------------------
        # 5. Retorna tudo para o yas.py
        # ------------------------------------------------------

        return {
            "resposta": resposta_yasm,
            "perguntar": perguntar,
            "tipo_pergunta": (
                self.iniciativa.escolher_tipo_pergunta(
                    self.contexto.obter_assunto()
                )
                if perguntar
                else None
            ),
            "assunto": self.contexto.obter_assunto(),
            "contexto": self.contexto.resumo(),
            "historico": self.contexto.obter_historico()
        }

    # ==========================================================
    # CONTROLE
    # ==========================================================

    def limpar_contexto(self):
        """
        Limpa a conversa atual.

        A memória permanente NÃO é apagada.
        """

        self.contexto.limpar()

        self.iniciativa.registrar_resposta_normal()

    def limpar_memoria(self):
        """
        Apaga toda a memória permanente.
        """

        with self._lock:
            anterior = self.memoria
            self.memoria = self._memoria_padrao()
            if not self._salvar_memoria():
                self.memoria = anterior
                return False
            return True

    def estado(self):
        """
        Retorna informações úteis para testes/debug.
        """

        return {
            "assunto": self.contexto.obter_assunto(),
            "historico": self.contexto.obter_historico(),
            "ultima_fala_usuario": (
                self.contexto.ultima_fala_usuario()
            ),
            "ultima_fala_yasm": (
                self.contexto.ultima_fala_yasm()
            ),
            "memoria": deepcopy(self.memoria)
        }


# ==============================================================
# INSTÂNCIA GLOBAL
# ==============================================================

cerebro = CerebroYasm()
