from __future__ import annotations

from copy import deepcopy
import re
import unicodedata
from typing import Any

from agente.configuracao import SessaoConfiguracao

import audio_yasm as audio
import falas
import voz_yasm as voz

from memoria_yasm import (
    memoria,
    salvar_memoria,
)


# ============================================================
# CONFIGURAÇÕES
# ============================================================

_DESCRICOES_VOZ = {
    "kitsune:emilia": "Emilia, uma voz doce e gentil",
    "kitsune:frieren": "Frieren, uma voz calma e serena",
    "kitsune:violet": "Violet, uma voz elegante e expressiva",
}
OPCOES_VOZ = {
    str(indice): {"nome": _DESCRICOES_VOZ.get(identificador, identificador.partition(":")[2].title()),
                  "id": identificador}
    for indice, identificador in enumerate(voz.vozes_com_amostra(), start=1)
}
_sessao_configuracao: SessaoConfiguracao | None = None


# ============================================================
# UTILITÁRIOS
# ============================================================

def falar(texto: str) -> None:
    voz.falar(
        str(texto)
    )


def pergunta_variada(topico: str, *variantes: str) -> str:
    if _sessao_configuracao is None:
        return variantes[0]
    return _sessao_configuracao.formular(topico, variantes)


def ouvir(
    timeout: float = 10.0,
) -> str:

    try:

        resposta = audio.escutar(
            timeout=timeout,
            silencioso=True,
        )

        return str(
            resposta or ""
        ).strip()

    except Exception:

        return ""


def normalizar_resposta(
    texto: str,
) -> str:

    texto = str(
        texto or ""
    ).strip().lower()

    texto = unicodedata.normalize(
        "NFD",
        texto,
    )

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(
            caractere
        ) != "Mn"
    )

    texto = re.sub(
        r"[^\w\s]",
        " ",
        texto,
        flags=re.UNICODE,
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto.strip()


# ============================================================
# RESPOSTAS POSITIVAS
# ============================================================

RESPOSTAS_SIM = {
    "sim",
    "s",
    "claro",
    "claro que sim",
    "com certeza",
    "com certeza sim",
    "pode",
    "pode sim",
    "quero",
    "quero sim",
    "eu quero",
    "isso",
    "isso mesmo",
    "exatamente",
    "afirmativo",
    "positivo",
    "beleza",
    "beleza sim",
    "ok",
    "okay",
    "ta",
    "ta bom",
    "tá bom",
    "tudo bem",
    "sem problema",
    "pode ser",
    "por mim sim",
    "sim quero",
    "sim pode",
    "sim claro",
    "combinado",
}


# ============================================================
# RESPOSTAS NEGATIVAS
# ============================================================

RESPOSTAS_NAO = {
    "nao",
    "n",
    "nem",
    "negativo",
    "de jeito nenhum",
    "nem pensar",
    "não",
    "nao quero",
    "não quero",
    "nao quero isso",
    "não quero isso",
    "prefiro nao",
    "prefiro não",
    "melhor nao",
    "melhor não",
    "nao precisa",
    "não precisa",
    "nao gostaria",
    "não gostaria",
    "dispenso",
    "deixa pra la",
    "deixa pra lá",
    "pode deixar",
    "nao pode",
    "não pode",
    "sem",
}


# ============================================================
# PALAVRAS INDICADORAS
# ============================================================

PALAVRAS_SIM = {
    "sim",
    "claro",
    "quero",
    "pode",
    "beleza",
    "com certeza",
    "positivo",
    "afirmativo",
    "combinado",
    "exatamente",
}


PALAVRAS_NAO = {
    "nao",
    "não",
    "negativo",
    "dispenso",
    "de jeito nenhum",
    "nem",
}


# ============================================================
# DETECÇÃO DE SIM
# ============================================================

def resposta_sim(
    texto: str,
) -> bool:

    resposta = normalizar_resposta(
        texto
    )

    if not resposta:
        return False

    if resposta in RESPOSTAS_SIM:
        return True

    for frase in RESPOSTAS_SIM:

        frase_normalizada = normalizar_resposta(
            frase
        )

        if (
            resposta
            == frase_normalizada
        ):
            return True

    tokens = resposta.split()

    for palavra in PALAVRAS_SIM:

        palavra_normalizada = normalizar_resposta(
            palavra
        )

        if palavra_normalizada in tokens:
            return True

    return False


# ============================================================
# DETECÇÃO DE NÃO
# ============================================================

def resposta_nao(
    texto: str,
) -> bool:

    resposta = normalizar_resposta(
        texto
    )

    if not resposta:
        return False

    if resposta in RESPOSTAS_NAO:
        return True

    for frase in RESPOSTAS_NAO:

        frase_normalizada = normalizar_resposta(
            frase
        )

        if (
            resposta
            == frase_normalizada
        ):
            return True

    tokens = resposta.split()

    for palavra in PALAVRAS_NAO:

        palavra_normalizada = normalizar_resposta(
            palavra
        )

        if palavra_normalizada in tokens:
            return True

    return False


# ============================================================
# INTERPRETAÇÃO SIM/NÃO
# ============================================================

def interpretar_sim_nao(
    texto: str,
) -> bool | None:

    resposta = normalizar_resposta(
        texto
    )

    if not resposta:
        return None

    if resposta_nao(
        resposta
    ):
        return False

    if resposta_sim(
        resposta
    ):
        return True

    return None


# ============================================================
# PERGUNTA SIM/NÃO
# ============================================================

def perguntar_sim_nao(
    pergunta: str,
    padrao: bool = True,
    *,
    topico: str = "confirmacao",
    variantes: tuple[str, ...] = (),
    explicacao: str = "Isso adapta a Yasmin ao seu jeito de trabalhar.",
) -> bool:
    falhas = 0
    desvios = 0
    while falhas < 3:
        falar(pergunta_variada(topico, *(variantes or (pergunta,))))
        resposta = ouvir()
        resultado = interpretar_sim_nao(resposta)
        if resultado is not None:
            return resultado
        if resposta and _sessao_configuracao is not None and desvios < 2:
            falar(_sessao_configuracao.responder_desvio(resposta, explicacao))
            desvios += 1
            continue
        falhas += 1
        if falhas < 3:
            falar("Pode me dizer sim ou não? Se quiser, explique sua escolha.")
    return padrao


# ============================================================
# DETECÇÃO DE NÚMERO FALADO
# ============================================================

NUMEROS = {
    "zero": "0",
    "um": "1",
    "uma": "1",
    "primeiro": "1",
    "primeira": "1",
    "dois": "2",
    "duas": "2",
    "segundo": "2",
    "segunda": "2",
    "tres": "3",
    "três": "3",
    "terceiro": "3",
    "terceira": "3",
    "quatro": "4",
    "quarto": "4",
    "quarta": "4",
    "cinco": "5",
    "quinto": "5",
    "quinta": "5",
    "seis": "6",
    "sexto": "6",
    "sexta": "6",
}


def extrair_numero(
    texto: str,
) -> str | None:

    resposta = normalizar_resposta(
        texto
    )

    if not resposta:
        return None

    tokens = resposta.split()

    for token in tokens:

        if token in NUMEROS:

            return NUMEROS[
                token
            ]

    encontrado = re.search(
        r"\b([1-9]\d?)\b",
        resposta,
    )

    if encontrado:

        return encontrado.group(1)

    return None


# ============================================================
# INTERPRETAÇÃO DE OPÇÃO
# ============================================================

def interpretar_opcao(
    resposta: str,
    opcoes: dict[str, str],
) -> str | None:

    texto = normalizar_resposta(
        resposta
    )

    if not texto:
        return None

    for chave, descricao in opcoes.items():

        descricao_normalizada = normalizar_resposta(
            descricao
        )

        if (
            texto
            == descricao_normalizada
        ):
            return chave

        if f" {descricao_normalizada} " in f" {texto} ":
            return chave

    grupos = {

        "diretas": {
            "direta",
            "direto",
            "curta",
            "curtas",
            "objetiva",
            "objetivas",
            "rapida",
            "rapido",
            "rápida",
            "rápido",
            "sem enrolacao",
            "sem enrolação",
            "vai direto ao ponto",
            "seja objetiva",
            "seja objetivo",
            "quero algo curto",
            "respostas curtas",
            "respostas diretas",
        },

        "equilibradas": {
            "equilibrada",
            "equilibrado",
            "normal",
            "normais",
            "meio termo",
            "um pouco de cada",
            "na medida",
            "nem muito curta nem muito longa",
            "nao muito curta nem muito longa",
        },

        "detalhadas": {
            "detalhada",
            "detalhado",
            "detalhadas",
            "detalhados",
            "completa",
            "completo",
            "explicada",
            "explicado",
            "explicacoes",
            "explicação",
            "mais detalhes",
            "quero detalhes",
            "explique bem",
            "explique melhor",
            "quero uma explicacao completa",
            "quero uma explicação completa",
        },

        "seria": {
            "seria",
            "serio",
            "séria",
            "sério",
            "formal",
            "profissional",
            "mais seria",
            "mais sério",
            "mais formal",
        },

        "descontraida": {
            "descontraida",
            "descontraído",
            "descontraido",
            "casual",
            "informal",
            "divertida",
            "divertido",
            "amigavel",
            "amigável",
            "solta",
            "leve",
            "mais casual",
            "mais informal",
            "pode ser descontraida",
            "quero uma assistente descontraida",
        },

        "nao": {
            "nao",
            "não",
            "nunca",
            "nem",
            "de jeito nenhum",
        },

        "sim": {
            "sim",
            "claro",
            "quero",
            "pode",
            "com certeza",
            "sempre",
        },

        "as vezes": {
            "as vezes",
            "às vezes",
            "algumas vezes",
            "de vez em quando",
            "quando fizer sentido",
            "ocasionalmente",
            "na medida certa",
        },

        "iniciante": {
            "iniciante",
            "começando",
            "comecando",
            "sou iniciante",
            "sei pouco",
            "pouco conhecimento",
            "basico",
            "básico",
            "sou novato",
            "sou nova nessa area",
            "sou novo nessa area",
        },

        "intermediario": {
            "intermediario",
            "intermediário",
            "medio",
            "médio",
            "já tenho conhecimento",
            "ja tenho conhecimento",
            "sei o basico",
            "sei o básico",
            "tenho alguma experiencia",
            "tenho alguma experiência",
        },

        "avancado": {
            "avancado",
            "avançado",
            "experiente",
            "sou experiente",
            "sei bastante",
            "tenho bastante experiencia",
            "tenho bastante experiência",
            "tenho conhecimento avancado",
            "tenho conhecimento avançado",
        },

        "programacao": {
            "programacao",
            "programação",
            "programar",
            "codigo",
            "código",
            "desenvolvimento",
            "programacao de computadores",
        },

        "estudos": {
            "estudo",
            "estudos",
            "estudar",
            "aprendizado",
            "aprender",
            "escola",
            "faculdade",
            "curso",
        },

        "trabalho": {
            "trabalho",
            "trabalhar",
            "profissional",
            "empresa",
            "emprego",
        },

        "entretenimento": {
            "entretenimento",
            "diversao",
            "diversão",
            "divertir",
            "filmes",
            "series",
            "séries",
            "jogos",
            "musica",
            "música",
        },

        "assistente pessoal": {
            "assistente pessoal",
            "uso pessoal",
            "dia a dia",
            "rotina",
            "organização pessoal",
            "organizacao pessoal",
        },

        "um pouco de tudo": {
            "um pouco de tudo",
            "tudo",
            "varias coisas",
            "várias coisas",
            "de tudo",
            "qualquer coisa",
            "varios usos",
            "vários usos",
        },

        "primeira": {
            "primeira",
            "primeiro",
            "numero um",
            "número um",
            "voz um",
            "voz 1",
        },

        "segunda": {
            "segunda",
            "segundo",
            "numero dois",
            "número dois",
            "voz dois",
            "voz 2",
        },

        "terceira": {
            "terceira",
            "terceiro",
            "numero tres",
            "número três",
            "voz tres",
            "voz 3",
        },
    }

    for chave, palavras in grupos.items():

        for palavra in palavras:

            palavra_normalizada = normalizar_resposta(
                palavra
            )

            if f" {palavra_normalizada} " in f" {texto} ":

                for opcao, descricao in opcoes.items():

                    descricao_n = normalizar_resposta(
                        descricao
                    )

                    if chave == descricao_n or (chave in {"sim", "nao"} and descricao_n.startswith(chave + " ")):
                        return opcao

    # Numeros so valem como escolha explicita, nao como parte de uma frase.
    if re.fullmatch(r"(?:(?:opcao|numero|voz|a|o)\s+)*[\w]+", texto):
        numero = extrair_numero(texto)
        if numero in opcoes:
            return numero

    return None


# ============================================================
# PERGUNTA DE OPÇÃO
# ============================================================

def perguntar_opcao(
    pergunta: str,
    opcoes: dict[str, str],
    padrao: str,
    *,
    topico: str = "opcao",
    variantes: tuple[str, ...] = (),
    explicacao: str = "A escolha determina como vou ajudar nas suas tarefas.",
) -> str:
    falhas = 0
    desvios = 0
    while falhas < 3:
        falar(pergunta_variada(topico, *(variantes or (pergunta,))))
        resposta = ouvir()
        resultado = interpretar_opcao(resposta, opcoes)
        if resultado is not None:
            return resultado
        if resposta and _sessao_configuracao is not None and desvios < 2:
            falar(_sessao_configuracao.responder_desvio(resposta, explicacao))
            desvios += 1
            continue
        falhas += 1
        if falhas < 3:
            falar("Ainda não entendi a opção. Pode falar o número ou explicar com suas palavras.")
    return padrao


# ============================================================
# CONFIGURAÇÃO
# ============================================================

def configuracao_concluida() -> bool:

    return bool(
        memoria
        .get(
            "configuracao",
            {}
        )
        .get(
            "concluida",
            False
        )
    )


# ============================================================
# NOME DO USUÁRIO
# ============================================================

def perguntar_nome() -> str:

    for _ in range(3):

        falar(pergunta_variada("nome_usuario",
              "Antes de começarmos, como posso chamar você?",
              "Como você gosta de ser chamado quando estamos trabalhando?",
              "Qual nome devo usar para falar com você?"))

        resposta = ouvir()

        resposta = resposta.strip(
            " .,!?;"
        )

        if not resposta:
            continue

        return resposta.title()

    return "Amigo"


# ============================================================
# NOME DA ASSISTENTE
# ============================================================

def perguntar_nome_assistente() -> str:

    for _ in range(3):

        falar(pergunta_variada("nome_assistente",
              "E como você gostaria de me chamar?",
              "Quer continuar me chamando de Yasmin ou prefere outro nome?",
              "Que nome devo usar para me apresentar a você?"))

        resposta = ouvir()

        resposta = resposta.strip(
            " .,!?;"
        )

        if not resposta:
            continue

        return resposta.title()

    return "Yasm"


# ============================================================
# PERSONALIDADE
# ============================================================

def perguntar_personalidade() -> str:

    opcoes = {
        "1": "seria",
        "2": "descontraida",
        "3": "equilibrada",
    }

    resultado = perguntar_opcao(
        "Quer que eu converse de modo sério, descontraído ou equilibrado?",
        opcoes,
        "3",
        topico="personalidade",
        variantes=("Quer que eu converse de modo sério, descontraído ou equilibrado?",
                   "Durante uma revisão de código, prefere um tom mais profissional, leve ou um meio-termo?",
                   "Qual tom combina com você: sério, descontraído ou equilibrado?"),
        explicacao="O tom muda a conversa, sem alterar minhas verificações técnicas.",
    )

    return {
        "1": "seria",
        "2": "descontraida",
        "3": "equilibrada",
    }[resultado]


# ============================================================
# TAMANHO DAS RESPOSTAS
# ============================================================

def perguntar_tamanho_resposta() -> str:

    opcoes = {
        "1": "diretas",
        "2": "equilibradas",
        "3": "detalhadas",
    }

    resultado = perguntar_opcao(
        "Ao explicar código, prefere respostas diretas, equilibradas ou detalhadas?",
        opcoes,
        "2",
        topico="tamanho_respostas",
        variantes=("Ao explicar código, prefere respostas diretas, equilibradas ou detalhadas?",
                   "Quando eu encontrar um erro, quer um resumo direto ou uma explicação detalhada? Também posso equilibrar os dois.",
                   "Quanto detalhe você quer nas minhas respostas: pouco, médio ou bastante?"),
        explicacao="Isso define quanto contexto técnico trago em cada resposta.",
    )

    return {
        "1": "diretas",
        "2": "equilibradas",
        "3": "detalhadas",
    }[resultado]


# ============================================================
# PESQUISA AUTOMÁTICA
# ============================================================

def perguntar_pesquisa() -> str:

    opcoes = {
        "1": "sim pesquise automaticamente",
        "2": "pergunte antes",
        "3": "nao pesquise",
    }

    resultado = perguntar_opcao(
        opcoes,
        "1",
        topico="pesquisa",
        variantes=("Para documentação e informações atuais, posso pesquisar automaticamente, perguntar antes ou não pesquisar. O que prefere?",
                   "Se eu precisar consultar uma API ou documentação na internet, devo pesquisar, pedir autorização antes ou evitar a pesquisa?",
                   "Como quer que eu trate buscas online: automáticas, após perguntar ou desativadas?"),
        explicacao="A pesquisa online ajuda com documentação atual; esta escolha controla quando posso usá-la.",
    )

    return resultado


# ============================================================
# CORRETOR
# ============================================================

def perguntar_corretor() -> bool:

    return perguntar_sim_nao(
        "Às vezes posso entender uma palavra ou frase "
        "de forma diferente do que você quis dizer. "
        "Nessas situações, quer que eu tente corrigir "
        "o que entendi antes de desistir?",
        topico="corretor",
        variantes=("Se eu ouvir errado um nome de comando ou ferramenta, quer que eu tente corrigir a transcrição?",
                   "Quer que eu tente recuperar nomes técnicos mal transcritos, como bibliotecas e comandos?",
                   "Quando a fala sair confusa, devo sugerir uma correção antes de desistir?"),
        explicacao="A correção tenta recuperar a transcrição; ações incertas ainda pedem esclarecimento.",
    )


# ============================================================
# INICIATIVA
# ============================================================

def perguntar_iniciativa() -> str:

    opcoes = {
        "1": "sim",
        "2": "as vezes",
        "3": "nao",
    }

    return perguntar_opcao(
        "Como você prefere?",
        opcoes,
        "2",
        topico="iniciativa",
        variantes=("Quer que eu sugira próximos passos durante uma tarefa: sim, às vezes ou não?",
                   "Ao trabalharmos num projeto, devo propor pequenas melhorias por iniciativa própria?",
                   "Quanto de iniciativa você quer de mim: sempre, quando fizer sentido ou nunca?"),
        explicacao="Sugestões não executam mudanças perigosas sem sua confirmação.",
    )


# ============================================================
# INTERRUPÇÃO
# ============================================================

def perguntar_interrupcao() -> bool:

    return perguntar_sim_nao(
        "Quando eu estiver falando, "
        "você quer poder me interromper falando por cima?",
        topico="interrupcao",
        variantes=("Se eu estiver explicando algo, quer poder me interromper pela voz?",
                   "Quer interromper minhas respostas faladas quando já tiver entendido?",
                   "Durante uma explicação longa, devo aceitar que você fale por cima para interromper?"),
        explicacao="Isso controla apenas a fala, não interrompe alterações em andamento sem verificar o estado.",
    )


# ============================================================
# MEMÓRIA
# ============================================================

def perguntar_memoria() -> bool:

    return perguntar_sim_nao(
        "Você quer que eu memorize algumas informações "
        "sobre você para melhorar nossas conversas futuras?",
        topico="memoria",
        variantes=("Quer que eu lembre suas preferências e projetos para futuras sessões?",
                   "Posso guardar o que você me ensinar sobre seu jeito de programar?",
                   "Deseja ativar memória para eu aproveitar preferências e experiências em próximos trabalhos?"),
        explicacao="A memória guarda preferências e fatos úteis quando você permitir; dados do projeto continuam na própria aplicação.",
    )


def perguntar_tipo_memoria() -> str | None:

    opcoes = {
        "1": "tudo",
        "2": "preferencias e rotina",
        "3": "somente o que eu indicar",
    }

    resultado = perguntar_opcao(
        "Como você prefere?",
        opcoes,
        "3",
        topico="tipo_memoria",
        variantes=("O que posso lembrar: tudo que você pedir, suas preferências e rotina, ou somente fatos indicados explicitamente?",
                   "Para a memória, prefere registrar suas escolhas de trabalho ou apenas informações que você mandar guardar?",
                   "Quer memória ampla, de preferências e rotina, ou somente do que indicar?"),
        explicacao="Você pode corrigir ou pedir que eu esqueça fatos; não preciso copiar arquivos inteiros para a memória.",
    )

    return {
        "1": "tudo",
        "2": "preferencias e rotina",
        "3": "somente o que eu indicar",
    }[resultado]


# ============================================================
# INICIALIZAÇÃO COM WINDOWS
# ============================================================

def perguntar_inicializacao() -> bool:

    return perguntar_sim_nao(
        "Você quer que eu inicie automaticamente "
        "junto com o Windows?",
        topico="inicializacao",
        variantes=("Quer que eu inicie junto com o Windows para deixar o Workspace pronto?",
                   "Devo abrir automaticamente quando você ligar o computador?",
                   "Você prefere iniciar a Yasmin com o Windows ou só quando precisar?"),
        explicacao="Isso altera apenas quando a Yasmin é iniciada; não modifica seus projetos.",
    )


# ============================================================
# SAUDAÇÃO
# ============================================================

def perguntar_saudacao() -> bool:

    return perguntar_sim_nao(
        "Quando eu iniciar, você quer que eu "
        "dê uma mensagem de boas-vindas?",
        topico="saudacao",
        variantes=("Quando eu iniciar, quer ouvir uma saudação?",
                   "Prefere que eu cumprimente você ao abrir o Workspace?",
                   "Ao começar a sessão, devo falar uma mensagem de boas-vindas?"),
        explicacao="A saudação é opcional e não altera o funcionamento das ferramentas.",
    )


# ============================================================
# PRINCIPAL USO
# ============================================================

def perguntar_uso_principal() -> str:

    opcoes = {
        "1": "assistente pessoal",
        "2": "estudos",
        "3": "programacao",
        "4": "trabalho",
        "5": "entretenimento",
        "6": "um pouco de tudo",
    }

    falar(
        "Também quero entender para que você "
        "pretende usar mais a Yasm."
    )

    falar(
        "Pode ser para estudos, programação, trabalho, "
        "uso pessoal, entretenimento ou um pouco de tudo."
    )

    resultado = perguntar_opcao(
        "Qual será o principal uso?",
        opcoes,
        "6",
    )

    return opcoes[
        resultado
    ]


# ============================================================
# NÍVEL TÉCNICO
# ============================================================

def perguntar_nivel_tecnico() -> str:

    opcoes = {
        "1": "iniciante",
        "2": "intermediario",
        "3": "avancado",
    }

    falar(
        "Agora quero entender seu nível de conhecimento "
        "em tecnologia."
    )

    falar(
        "Isso me ajuda a adaptar a forma como explico "
        "assuntos técnicos para você."
    )

    falar(
        "Pode dizer iniciante, intermediário ou avançado, "
        "ou explicar seu nível com suas próprias palavras."
    )

    resultado = perguntar_opcao(
        "Como você se considera?",
        opcoes,
        "1",
    )

    return opcoes[
        resultado
    ]


# ============================================================
# VOZ
# ============================================================

def testar_voz(
    numero: str,
) -> None:

    configuracao = OPCOES_VOZ.get(
        numero
    )

    if not configuracao:
        return

    voz.definir_voz_temporaria(
        configuracao["id"]
    )

    if not voz.reproduzir_amostra(configuracao["id"]):
        falar(
            f"Essa e a {configuracao['nome']}. "
            "Veja se voce gosta desta voz."
        )


def escolher_voz() -> str:

    if not OPCOES_VOZ:
        falar("Não encontrei amostras de voz compatíveis com o modelo instalado.")
        return voz.obter_voz_atual()

    falar(
        "Agora chegou a hora de escolher minha voz."
    )

    falar(
        "Vou testar algumas opções para você. "
        "Você não precisa saber o nome técnico delas."
    )

    for numero in OPCOES_VOZ:

        testar_voz(
            numero
        )

    falar(
        "Qual dessas vozes combina mais com a Yasm "
        "para você?"
    )

    ordinais = ("primeira", "segunda", "terceira", "quarta", "quinta")
    opcoes = {numero: ordinais[indice] if indice < len(ordinais) else numero
              for indice, numero in enumerate(OPCOES_VOZ)}

    escolha = perguntar_opcao(
        "Pode dizer primeira, segunda, terceira "
        "ou o número correspondente.",
        opcoes,
        "1",
    )

    voz_escolhida = OPCOES_VOZ[
        escolha
    ]["id"]

    voz.definir_voz(
        voz_escolhida
    )

    return voz_escolhida


# ============================================================
# RESUMO
# ============================================================

def _valor_humano_sim_nao(
    valor: Any,
) -> str:

    if valor is True:
        return "sim"

    if valor is False:
        return "não"

    return str(valor)


def resumo_configuracao(
    configuracao: dict[str, Any],
) -> str:

    usuario = configuracao[
        "usuario"
    ]

    assistente = configuracao[
        "assistente"
    ]

    preferencias = configuracao[
        "preferencias"
    ]

    pesquisa = preferencias[
        "pesquisa_automatica"
    ]

    if pesquisa is True:
        pesquisa_texto = "sim"
    elif pesquisa is False:
        pesquisa_texto = "não"
    else:
        pesquisa_texto = str(
            pesquisa
        )

    iniciativa = preferencias.get(
        "iniciativa",
        "às vezes",
    )

    interrupcao = _valor_humano_sim_nao(
        preferencias.get(
            "interrupcao",
            False,
        )
    )

    memoria_ativa = _valor_humano_sim_nao(
        preferencias.get(
            "memoria_ativa",
            False,
        )
    )

    corretor = _valor_humano_sim_nao(
        preferencias.get(
            "corretor_ativo",
            False,
        )
    )

    return (
        f"Seu nome é {usuario['nome']}. "
        f"Meu nome será {assistente['nome']}. "
        f"Minha personalidade será "
        f"{preferencias['personalidade']}. "
        f"Minhas respostas serão "
        f"{preferencias['tamanho_respostas']}. "
        f"Pesquisa automática: "
        f"{pesquisa_texto}. "
        f"Corretor de fala: "
        f"{corretor}. "
        f"Iniciativa: "
        f"{iniciativa}. "
        f"Interrupção: "
        f"{interrupcao}. "
        f"Memória: "
        f"{memoria_ativa}. "
        f"Uso principal: "
        f"{preferencias['uso_principal']}. "
        f"Nível técnico: "
        f"{preferencias['nivel_tecnico']}."
    )


# ============================================================
# EXECUÇÃO DA CONFIGURAÇÃO
# ============================================================

def executar_configuracao(agente=None, conversacao=None) -> bool:
    """Apresenta por voz a sessão conduzida pelo Agent Core."""
    if configuracao_concluida():
        return False

    sessao = SessaoConfiguracao(agente, conversacao, vozes=OPCOES_VOZ)
    falar("Olá! Sou a Yasmin, sua assistente para trabalhar no computador e desenvolver projetos. "
          "Vamos ajustar nossa conversa. Responda naturalmente e pode perguntar algo no meio.")
    while not sessao.concluida and not sessao.cancelada:
        falar(sessao.formular())
        resposta = ouvir()
        retorno = sessao.receber(resposta)
        if retorno.acao == "testar_voz":
            if retorno.parametro in OPCOES_VOZ:
                testar_voz(retorno.parametro)
            else:
                falar("Não encontrei essa amostra. Pode escolher uma das opções que mencionei.")
            continue
        if retorno.cancelada:
            falar(retorno.mensagem)
            return False
        if retorno.mensagem:
            falar(retorno.mensagem)

    if not sessao.concluida:
        return False
    nova_configuracao = sessao.configuracao()
    voz_id = nova_configuracao["voz"]["id"] or voz.obter_voz_atual()
    nova_configuracao["voz"]["id"] = voz_id
    novos_dados = deepcopy(memoria)
    for chave, valor in nova_configuracao.items():
        if isinstance(valor, dict):
            novos_dados.setdefault(chave, {}).update(valor)
        else:
            novos_dados[chave] = valor
    if not salvar_memoria(novos_dados):
        falar("Não consegui salvar suas preferências agora. Podemos tentar novamente depois.")
        return False
    memoria.clear()
    memoria.update(novos_dados)
    voz.definir_voz(voz_id)
    if conversacao is not None:
        conversacao.aplicar_preferencias(nova_configuracao["preferencias"])
    sessao.sincronizar_preferencias(nova_configuracao["preferencias"])
    falar(f"Pronto, {nova_configuracao['usuario']['nome']}. "
          "Suas preferências foram salvas. Podemos começar a trabalhar.")
    return True


# ============================================================
# API
# ============================================================

def precisa_configurar() -> bool:

    return not configuracao_concluida()


def iniciar(agente=None, conversacao=None) -> bool:

    return executar_configuracao(agente=agente, conversacao=conversacao)


# ============================================================
# TESTE DIRETO
# ============================================================

if __name__ == "__main__":

    executar_configuracao()
