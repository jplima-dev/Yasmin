"""Configuração conversada: perguntas, interpretação e estado pertencem ao agente."""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import unicodedata
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("yasm.agente")


def _normalizar(texto: str) -> str:
    base = unicodedata.normalize("NFKD", str(texto).casefold())
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", "".join(
        letra for letra in base if not unicodedata.combining(letra)))).strip()


@dataclass(frozen=True)
class Pergunta:
    chave: str
    variantes: tuple[str, ...]
    explicacao: str
    opcoes: tuple[tuple[str, tuple[str, ...]], ...] = ()
    padrao: Any = None
    tipo: str = "opcao"


@dataclass(frozen=True)
class RespostaConfiguracao:
    aceita: bool
    mensagem: str = ""
    concluida: bool = False
    cancelada: bool = False
    acao: str = ""
    parametro: str = ""


PERGUNTAS_BASE = (
    Pergunta("nome_usuario", ("Como posso chamar você?", "Qual nome prefere que eu use?",
             "Antes de trabalharmos juntos, como você gosta de ser chamado?"),
             "Uso seu nome para tornar a conversa mais pessoal.", padrao="Amigo", tipo="nome"),
    Pergunta("nome_assistente", ("Quer continuar me chamando de Yasmin ou prefere outro nome?",
             "Que nome devo usar quando conversar com você?", "Como você gostaria de me chamar?"),
             "Você pode manter Yasmin ou escolher outro nome.", padrao="Yasmin", tipo="nome"),
    Pergunta("personalidade", ("Ao revisar código, prefere que eu converse de modo sério, leve ou equilibrado?",
             "Qual tom combina com você: profissional, descontraído ou equilibrado?",
             "Durante o trabalho, quer um jeito de conversar mais sério, leve ou um meio-termo?"),
             "O tom muda a conversa, sem mudar a verificação técnica.",
             (("seria", ("serio", "seria", "formal", "profissional")),
              ("descontraida", ("leve", "descontraida", "informal", "divertida")),
              ("equilibrada", ("equilibrado", "equilibrada", "meio termo", "depende"))), "equilibrada"),
    Pergunta("tamanho_respostas", ("Quando eu explicar código, prefere respostas diretas, equilibradas ou detalhadas?",
             "Ao encontrar um erro, quer um resumo curto, uma explicação completa ou algo entre os dois?",
             "Quanto detalhe devo trazer nas respostas: pouco, médio ou bastante?"),
             "Isso define quanto contexto técnico apresento.",
             (("diretas", ("direta", "diretas", "curta", "curtas", "breve", "objetiva", "rapida")),
              ("equilibradas", ("equilibrada", "equilibradas", "medio", "intermediaria", "meio termo")),
              ("detalhadas", ("detalhada", "detalhadas", "completa", "completas", "longa", "muito detalhe"))),
             "equilibradas"),
    Pergunta("pesquisa_automatica", ("Quando eu precisar de documentação atual, posso pesquisar automaticamente, perguntar antes ou não pesquisar?",
             "Para consultar a internet durante uma tarefa de desenvolvimento, devo pesquisar, pedir permissão antes ou evitar buscas?",
             "Como prefere as buscas online: automáticas, após perguntar, ou desativadas?"),
             "A internet continua disponível; esta escolha controla quando consultá-la.",
             (("automatico", ("automaticamente", "automatico", "pesquise", "pode pesquisar", "sempre")),
              ("perguntar", ("pergunte", "perguntar", "pedir permissao", "pede antes", "avise antes")),
              ("desativado", ("nao pesquise", "nao pesquisar", "evite", "desativar", "nunca"))), "perguntar"),
    Pergunta("corretor_ativo", ("Se um comando ou nome técnico sair errado na transcrição, quer que eu tente corrigir?",
             "Quer que eu tente recuperar nomes de bibliotecas e comandos mal reconhecidos pela voz?",
             "Quando a fala sair confusa, devo tentar uma correção antes de pedir que repita?"),
             "Correções incertas ainda podem exigir esclarecimento.", padrao=True, tipo="sim_nao"),
    Pergunta("iniciativa", ("Ao trabalharmos num projeto, devo sugerir próximos passos sempre, às vezes ou nunca?",
             "Quer que eu proponha melhorias por iniciativa própria, quando fizer sentido, ou prefira esperar?",
             "Quanto de iniciativa você quer de mim durante tarefas de programação?"),
             "Sugestões não executam ações perigosas sem confirmação.",
             (("sim", ("sempre", "sim", "bastante", "pode sugerir")),
              ("as vezes", ("as vezes", "quando fizer sentido", "de vez em quando", "moderadamente")),
              ("nao", ("nunca", "nao", "prefiro esperar", "so quando pedir"))), "as vezes"),
    Pergunta("interrupcao", ("Se eu estiver explicando algo, quer poder me interromper pela voz?",
             "Durante uma explicação longa, devo aceitar que você fale por cima?",
             "Quer interromper minhas respostas faladas quando já tiver entendido?"),
             "Isto controla a fala e não descarta uma operação em andamento.", padrao=True, tipo="sim_nao"),
    Pergunta("memoria_ativa", ("Quer que eu lembre suas preferências e projetos em futuras sessões?",
             "Posso guardar o que você me ensinar sobre seu jeito de programar?",
             "Deseja ativar a memória para aproveitar preferências e experiências depois?"),
             "A memória guarda fatos úteis que você permitir; dados atuais do projeto ficam no aplicativo.",
             padrao=False, tipo="sim_nao"),
    Pergunta("tipo_memoria", ("O que posso lembrar: preferências e rotina, tudo que pedir, ou apenas fatos que você indicar?",
             "Prefere uma memória ampla, das suas preferências, ou somente do que mandar guardar?",
             "Para a memória, devo registrar seu jeito de trabalhar ou só informações indicadas explicitamente?"),
             "Você pode corrigir ou esquecer informações guardadas.",
             (("tudo", ("tudo", "ampla", "geral")),
              ("preferencias e rotina", ("preferencias", "rotina", "meu jeito", "como trabalho")),
              ("somente o que eu indicar", ("somente", "apenas", "so quando eu pedir", "explicitamente"))),
             "somente o que eu indicar"),
    Pergunta("inicializar_windows", ("Quer que eu inicie com o Windows e deixe o Workspace pronto?",
             "Devo abrir automaticamente quando ligar o computador?",
             "Prefere iniciar a Yasmin com o Windows ou só quando precisar?"),
             "Essa escolha controla apenas a inicialização.", padrao=False, tipo="sim_nao"),
    Pergunta("saudacao_inicio", ("Quando eu iniciar, quer ouvir uma saudação?",
             "Prefere que eu cumprimente você ao abrir o Workspace?",
             "Ao começar uma sessão, devo falar uma mensagem de boas-vindas?"),
             "A saudação é opcional.", padrao=True, tipo="sim_nao"),
    Pergunta("uso_principal", ("Em desenvolvimento, com o que mais devo ajudar: depurar código, organizar projetos, automatizar tarefas ou aprender tecnologias?",
             "No seu trabalho como dev, sua prioridade é revisar código, cuidar do Workspace, automatizar rotinas ou estudar programação?",
             "Qual parte do desenvolvimento merece mais apoio: código, projetos, automação, aprendizado ou um pouco de tudo?"),
             "Isso me ajuda a priorizar ferramentas e explicações para você.",
             (("revisao e depuracao", ("codigo", "programacao", "revisar", "revisao", "debug", "depurar", "bugs", "erros")),
              ("projetos e workspace", ("projeto", "projetos", "workspace", "organizar", "arquivos")),
              ("automacao de desenvolvimento", ("automatizar", "automacao", "rotina", "tarefas repetitivas", "scripts")),
              ("aprendizado de tecnologias", ("aprender", "estudar", "tecnologias", "iniciante", "ensinar")),
              ("um pouco de tudo", ("tudo", "varias coisas", "um pouco de tudo"))), "um pouco de tudo"),
    Pergunta("nivel_tecnico", ("Em programação, você se considera iniciante, intermediário ou avançado?",
             "Quanto contexto técnico você já domina: está começando, tem alguma experiência ou é avançado?",
             "Para calibrar minhas explicações, qual é seu nível de desenvolvimento?"),
             "Adapto a profundidade das explicações ao seu nível.",
             (("iniciante", ("iniciante", "comecando", "novo", "aprendendo", "primeiros passos")),
              ("intermediario", ("intermediario", "alguma experiencia", "ja programo", "medio")),
              ("avancado", ("avancado", "experiente", "senior", "profissional"))), "iniciante"),
)


class SessaoConfiguracao:
    """Máquina de diálogo da configuração, independente da interface de voz."""

    def __init__(self, agente=None, conversacao=None, *, vozes: dict[str, dict] | None = None,
                 semente: int | None = None):
        self.agente = agente
        self.conversacao = conversacao
        self._semente = secrets.randbits(64) if semente is None else semente
        self._perguntas = list(PERGUNTAS_BASE)
        if vozes:
            opcoes = tuple((item["id"], (numero, item["nome"], item["id"],
                     ("primeira", "segunda", "terceira", "quarta", "quinta")[indice]
                     if indice < 5 else numero)) for indice, (numero, item) in enumerate(vozes.items()))
            nomes = ", ".join(f"{numero}: {item['nome']}" for numero, item in vozes.items())
            self._perguntas.append(Pergunta("voz", (
                f"Qual voz combina comigo? Você pode escolher entre {nomes}.",
                f"Para minha voz, qual destas opções prefere: {nomes}?",
                f"Escolha a voz que gostaria de ouvir: {nomes}."),
                "Pode pedir uma amostra dizendo 'teste a voz 1', por exemplo.",
                opcoes, next(iter(vozes.values()))["id"]))
        self._indice = 0
        self._tentativas = 0
        self._rodadas: dict[str, int] = {}
        self.respostas: dict[str, Any] = {}
        self.pergunta_atual = ""
        self.cancelada = False

    @property
    def topico_atual(self) -> str:
        return self._perguntas[self._indice].chave if self._indice < len(self._perguntas) else ""

    @property
    def concluida(self) -> bool:
        return self._indice >= len(self._perguntas) and not self.cancelada

    def formular(self, topico: str | None = None, variantes: tuple[str, ...] | None = None) -> str:
        """Formula a pergunta atual; argumentos antigos ficam para compatibilidade."""
        pergunta = self._perguntas[self._indice]
        if topico is not None and variantes is not None:
            base, chave = variantes, topico
        else:
            base, chave = pergunta.variantes, pergunta.chave
        rodada = self._rodadas.get(chave, 0)
        digest = hashlib.blake2b(chave.encode(), digest_size=8).digest()
        inicio = (self._semente + int.from_bytes(digest, "big")) % len(base)
        texto = base[(inicio + rodada) % len(base)]
        self._rodadas[chave] = rodada + 1
        self.pergunta_atual = texto
        if self.conversacao is not None:
            self.conversacao.registrar_fala_assistente(texto)
        if self.agente is not None:
            self.agente.estado.contexto_imediato["configuracao_topico"] = pergunta.chave
        return texto

    def _interpretar(self, pergunta: Pergunta, texto: str) -> Any:
        normal = _normalizar(texto)
        if pergunta.tipo == "nome":
            nome = re.sub(r"^(?:meu nome e|pode me chamar de|me chame de|eu sou|chame me de|prefiro|quero te chamar de|vou te chamar de|seu nome sera)\s+", "", normal)
            return nome.title()[:60] if 1 <= len(nome) <= 60 and not re.search(r"\b(?:nao sei|qual|porque|por que)\b", nome) else None
        if pergunta.tipo == "sim_nao":
            if re.search(r"\b(?:nao|nunca|jamais|desativar|prefiro que nao|so quando eu (?:pedir|precisar))\b", normal):
                return False
            if re.search(r"\b(?:sim|pode|claro|quero|gostaria|ativar|com certeza)\b", normal):
                return True
            return None
        if pergunta.chave == "pesquisa_automatica":
            if re.search(r"\bnao\s+(?:me\s+)?pergunt", normal):
                return "automatico"
            if re.search(r"\b(?:antes|permissao|autoriza|pergunt)", normal):
                return "perguntar"
            if re.search(r"\b(?:nao|nunca|evite)\b.*\b(?:pesquis|internet|busca)", normal):
                return "desativado"
        if pergunta.chave == "uso_principal" and re.search(r"\b(?:tudo|varias|um pouco de cada)\b", normal):
            return "um pouco de tudo"
        if normal.isdigit():
            indice = int(normal) - 1
            return pergunta.opcoes[indice][0] if 0 <= indice < len(pergunta.opcoes) else None
        ocorrencias = []
        for valor, aliases in pergunta.opcoes:
            for alias in aliases:
                match = re.search(r"(?<!\w)" + re.escape(_normalizar(alias)) + r"(?!\w)", normal)
                if match:
                    ocorrencias.append((match.start(), len(alias), valor))
        if not ocorrencias:
            return None
        if pergunta.chave == "uso_principal" and len({valor for _, _, valor in ocorrencias}) > 1:
            return "um pouco de tudo"
        ocorrencias.sort(key=lambda item: (-item[1], item[0]))
        return ocorrencias[0][2]

    def _confirmar(self, chave: str, valor: Any) -> str:
        """Confirma a escolha com uma fala contextual, sem repetir a mesma frase."""
        if chave == "nome_usuario":
            frases = (f"Prazer, {valor}.", f"Combinado, vou chamar você de {valor}.")
        elif chave == "nome_assistente":
            frases = (f"Pode me chamar de {valor}.", f"Certo, {valor} será meu nome com você.")
        elif chave == "personalidade":
            frases = (f"Vou conversar de forma {valor}, inclusive nas tarefas técnicas.",
                      f"Certo, ajustei meu tom para {valor}.")
        elif chave == "tamanho_respostas":
            frases = (f"Minhas explicações serão {valor}.",
                      f"Entendi o nível de detalhe: respostas {valor}.")
        elif chave == "pesquisa_automatica":
            modo = {"automatico": "pesquisar quando precisar",
                    "perguntar": "perguntar antes de pesquisar",
                    "desativado": "evitar buscas online"}[valor]
            frases = (f"Certo, vou {modo}.", f"Para informações atuais, vou {modo}.")
        elif chave == "memoria_ativa":
            frases = (("Posso aproveitar suas preferências em sessões futuras.",
                       "Certo, vou usar a memória para escolhas úteis.") if valor else
                      ("Tudo bem, não vou guardar preferências para futuras sessões.",
                       "Certo, vou manter estas escolhas apenas na configuração atual."))
        elif chave == "uso_principal":
            frases = (f"Vou dar mais atenção a {valor} no seu fluxo de desenvolvimento.",
                      f"Entendi sua prioridade como dev: {valor}.")
        elif chave == "nivel_tecnico":
            frases = (f"Vou calibrar as explicações para o nível {valor}.",
                      f"Certo, explicarei assuntos técnicos pensando no seu nível {valor}.")
        elif chave == "voz":
            frases = ("Boa escolha de voz.", "Certo, essa será minha voz.")
        elif isinstance(valor, bool):
            tema = {"corretor_ativo": "corrigir transcrições incertas",
                    "interrupcao": "aceitar interrupções na fala",
                    "inicializar_windows": "iniciar com o Windows",
                    "saudacao_inicio": "cumprimentar você ao iniciar"}.get(chave, chave)
            frases = ((f"Certo, vou {tema}.", f"Entendido, posso {tema}.") if valor else
                      (f"Certo, não vou {tema}.", f"Entendido, deixarei de {tema}."))
        elif chave == "tipo_memoria":
            frases = (f"Vou guardar {valor}.", f"Minha memória ficará limitada a {valor}.")
        elif chave == "iniciativa":
            descricao = {"sim": "sugerir próximos passos",
                         "as vezes": "sugerir algo quando fizer sentido",
                         "nao": "esperar sua orientação"}[valor]
            frases = (f"Vou {descricao}.", f"Durante o trabalho, vou {descricao}.")
        else:
            frases = ("Entendi.", "Certo.")
        indice = (self._semente + self._indice) % len(frases)
        return frases[indice]

    def responder_desvio(self, texto: str, explicacao: str) -> str:
        normal = _normalizar(texto)
        if re.search(r"\b(?:por que|pra que|para que|qual motivo|o que significa)\b", normal):
            return explicacao
        if "nao sei" in normal or "tenho duvida" in normal:
            return f"Sem pressa. {explicacao} Pode responder com suas palavras."
        if self.agente is not None and self.conversacao is not None:
            try:
                return self.agente.conversar(texto, self.conversacao)
            except Exception as erro:
                log.debug("[AGENTE] Conversa na configuração indisponível: %s", erro)
        return f"Posso explicar antes de seguir. {explicacao}"

    def receber(self, texto: str) -> RespostaConfiguracao:
        if self.cancelada:
            return RespostaConfiguracao(False, "Configuração cancelada.", cancelada=True)
        if self.concluida:
            return RespostaConfiguracao(False, "A configuração já foi concluída.", concluida=True)
        pergunta = self._perguntas[self._indice]
        normal = _normalizar(texto)
        if normal in {"cancelar configuracao", "cancela configuracao", "quero cancelar a configuracao"}:
            self.cancelada = True
            return RespostaConfiguracao(False, "Certo, cancelei a configuração.", cancelada=True)
        if (self.conversacao is not None
                and getattr(self.conversacao, "confirmacao_pendente", False)
                and normal in {"sim", "nao", "pode ser", "aceito", "quero", "prefiro nao"}):
            return RespostaConfiguracao(False, self.responder_desvio(texto, pergunta.explicacao))
        if pergunta.chave == "voz" and (match := re.search(r"\b(?:teste|testar|amostra|ouvir)\b.*\b(\d+)\b", normal)):
            return RespostaConfiguracao(False, "Vou reproduzir essa amostra.", acao="testar_voz",
                                        parametro=match.group(1))
        if re.search(r"\b(?:por que|pra que|para que|o que significa|nao sei|tenho duvida)\b", normal):
            return RespostaConfiguracao(False, self.responder_desvio(texto, pergunta.explicacao))
        if "?" in texto or re.match(r"^(?:como|qual|quem|voce|me conte|fale|gostaria de saber|queria saber|me explica|pode explicar|o que)\b", normal):
            return RespostaConfiguracao(False, self.responder_desvio(texto, pergunta.explicacao))
        valor = self._interpretar(pergunta, texto)
        if valor is None:
            self._tentativas += 1
            if self._tentativas < 3:
                return RespostaConfiguracao(False, "Ainda não consegui ligar sua resposta a esta escolha. "
                                            + pergunta.explicacao)
            valor = pergunta.padrao
            aviso = f"Vou usar a opção padrão: {valor}. "
        else:
            aviso = ""
        self.respostas[pergunta.chave] = valor
        self._indice += 1
        self._tentativas = 0
        if pergunta.chave == "memoria_ativa" and not valor:
            self.respostas["tipo_memoria"] = None
            self._indice += 1
        if self.agente is not None:
            self.agente.estado.contexto_imediato["configuracao_respostas"] = dict(self.respostas)
        return RespostaConfiguracao(True, aviso + self._confirmar(pergunta.chave, valor),
                                    self.concluida)

    def configuracao(self) -> dict[str, Any]:
        if not self.concluida:
            raise RuntimeError("A configuração ainda não foi concluída")
        respostas = self.respostas
        pesquisa = {"automatico": True, "perguntar": "perguntar", "desativado": False}
        return {
            "usuario": {"nome": respostas["nome_usuario"]},
            "assistente": {"nome": respostas["nome_assistente"]},
            "voz": {"id": respostas.get("voz")},
            "preferencias": {
                "personalidade": respostas["personalidade"],
                "tamanho_respostas": respostas["tamanho_respostas"],
                "pesquisa_automatica": pesquisa[respostas["pesquisa_automatica"]],
                "corretor_ativo": respostas["corretor_ativo"],
                "iniciativa": respostas["iniciativa"],
                "interrupcao": respostas["interrupcao"],
                "memoria_ativa": respostas["memoria_ativa"],
                "tipo_memoria": respostas.get("tipo_memoria"),
                "inicializar_windows": respostas["inicializar_windows"],
                "saudacao_inicio": respostas["saudacao_inicio"],
                "uso_principal": respostas["uso_principal"],
                "nivel_tecnico": respostas["nivel_tecnico"],
            },
            "configuracao": {"concluida": True},
        }

    def sincronizar_preferencias(self, preferencias: dict) -> int:
        """Espelha escolhas no MySQL quando a memória está ativa."""
        if not preferencias.get("memoria_ativa") or self.agente is None:
            return 0
        chaves = ("personalidade", "tamanho_respostas", "pesquisa_automatica",
                  "iniciativa", "uso_principal", "nivel_tecnico")
        salvas = 0
        for chave in chaves:
            valor = preferencias.get(chave)
            if valor is None:
                continue
            try:
                salvas += bool(self.agente.memoria.guardar(
                    "preferencia", chave, valor, "configuracao", 0.8, 0.95))
            except Exception as erro:
                log.debug("[AGENTE] Preferência não persistida no MySQL: %s", erro)
        return salvas
