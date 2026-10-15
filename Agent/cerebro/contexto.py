# cerebro/contexto.py

from collections import deque


class ContextoYasm:
    """
    Mantém o contexto recente das conversas da Yasm.

    A ideia é evitar que a Yasm trate cada frase como uma conversa nova.
    """

    def __init__(self, limite=10):
        self.limite = limite
        self.historico = deque(maxlen=limite)
        self.assunto_atual = None

    def adicionar_usuario(self, texto):
        """Adiciona uma fala do usuário ao contexto."""
        if not texto:
            return

        self.historico.append({
            "papel": "usuario",
            "texto": texto
        })

    def adicionar_yasm(self, texto):
        """Adiciona uma fala da Yasm ao contexto."""
        if not texto:
            return

        self.historico.append({
            "papel": "yasm",
            "texto": texto
        })

    def definir_assunto(self, assunto):
        """Define o assunto atual da conversa."""
        self.assunto_atual = assunto

    def obter_assunto(self):
        """Retorna o assunto atual."""
        return self.assunto_atual

    def obter_historico(self):
        """Retorna uma cópia do histórico recente."""
        return [dict(item) for item in self.historico]

    def ultima_fala_usuario(self):
        """Retorna a última fala do usuário."""
        for item in reversed(self.historico):
            if item["papel"] == "usuario":
                return item["texto"]

        return None

    def ultima_fala_yasm(self):
        """Retorna a última fala da Yasm."""
        for item in reversed(self.historico):
            if item["papel"] == "yasm":
                return item["texto"]

        return None

    def limpar(self):
        """Limpa todo o contexto atual."""
        self.historico.clear()
        self.assunto_atual = None

    def resumo(self):
        """
        Retorna o contexto em formato de texto.
        Útil futuramente para mandar o contexto para um modelo de IA.
        """
        partes = []

        for item in self.historico:
            if item["papel"] == "usuario":
                partes.append(f"Usuário: {item['texto']}")
            else:
                partes.append(f"Yasm: {item['texto']}")

        if self.assunto_atual:
            partes.append(f"Assunto atual: {self.assunto_atual}")

        return "\n".join(partes)


# Instância global
contexto = ContextoYasm()
