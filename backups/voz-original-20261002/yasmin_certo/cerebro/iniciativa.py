# cerebro/iniciativa.py

import random


class IniciativaYasm:
    """
    Controla perguntas espontâneas da Yasm.

    A Yasm pode, de vez em quando, fazer uma pergunta complementar
    depois de responder algo.
    """

    def __init__(self, chance=0.35):
        # 35% de chance por padrão
        self.chance = chance
        self._ultima_foi_pergunta = False

    def deve_perguntar(self, texto_usuario=None, resposta=None):
        """
        Decide se a Yasm deve fazer uma pergunta complementar.

        Retorna True ou False.
        """

        if not isinstance(resposta, str) or not resposta:
            return False

        # Evita perguntas em respostas muito curtas.
        if len(resposta.strip()) < 20:
            return False

        # Evita ficar fazendo perguntas consecutivamente.
        if self._ultima_foi_pergunta or self._parece_que_ja_perguntou(resposta):
            return False

        return random.random() < self.chance

    def registrar_pergunta_iniciativa(self):
        self._ultima_foi_pergunta = True

    def registrar_resposta_normal(self):
        self._ultima_foi_pergunta = False

    def _parece_que_ja_perguntou(self, texto):
        """
        Verifica se a resposta já contém uma pergunta.
        """

        texto = texto.strip()

        return "?" in texto

    def escolher_tipo_pergunta(self, assunto=None):
        """
        Escolhe o tipo de continuação.
        """

        opcoes = [
            "mais_informacoes",
            "explicacao",
            "curiosidade",
            "continuacao"
        ]

        # Futuramente podemos usar o assunto para escolher melhor.
        return random.choice(opcoes)


# Instância global
iniciativa = IniciativaYasm()
