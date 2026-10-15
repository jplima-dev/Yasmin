from __future__ import annotations

import re
import unicodedata
from typing import Any

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

OPCOES_VOZ = {
    "1": {
        "nome": "Emilia, uma voz doce e gentil",
        "id": "kitsune:emilia",
    },
    "2": {
        "nome": "Frieren, uma voz calma e serena",
        "id": "kitsune:frieren",
    },
    "3": {
        "nome": "Violet, uma voz elegante e expressiva",
        "id": "kitsune:violet",
    },
}


# ============================================================
# UTILITÁRIOS
# ============================================================

def falar(texto: str) -> None:
    voz.falar(
        str(texto)
    )


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
) -> bool:

    for tentativa in range(3):

        falar(
            pergunta
        )

        resposta = ouvir()

        resultado = interpretar_sim_nao(
            resposta
        )

        if resultado is not None:
            return resultado

        if tentativa < 2:

            falar(
                "Não consegui entender. "
                "Você pode responder sim ou não."
            )

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
) -> str:

    for tentativa in range(3):

        falar(
            pergunta
        )

        resposta = ouvir()

        resultado = interpretar_opcao(
            resposta,
            opcoes,
        )

        if resultado is not None:
            return resultado

        if tentativa < 2:

            falar(
                "Não consegui identificar sua escolha. "
                "Pode falar o número ou explicar sua preferência "
                "com suas próprias palavras."
            )

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

        falar(
            "Antes de começarmos, como posso chamar você?"
        )

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

        falar(
            "E como você gostaria de me chamar?"
        )

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

    falar(
        "Agora quero saber como você prefere "
        "que eu converse com você."
    )

    falar(
        "Posso ser mais séria, mais descontraída "
        "ou ficar em um equilíbrio entre as duas."
    )

    resultado = perguntar_opcao(
        "Como você prefere?",
        opcoes,
        "3",
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

    falar(
        "Agora vou definir o tamanho das minhas respostas."
    )

    falar(
        "Você prefere que eu seja mais direta, "
        "equilibrada ou detalhada?"
    )

    resultado = perguntar_opcao(
        "Como você prefere?",
        opcoes,
        "2",
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

    falar(
        "Agora vamos decidir como devo agir "
        "quando eu não souber alguma coisa."
    )

    falar(
        "Posso pesquisar automaticamente, "
        "perguntar antes de pesquisar ou não pesquisar."
    )

    resultado = perguntar_opcao(
        "Qual dessas opções você prefere?",
        opcoes,
        "1",
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
        "o que entendi antes de desistir?"
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

    falar(
        "Agora quero saber o quanto você quer "
        "que eu participe ativamente das conversas."
    )

    falar(
        "Posso fazer perguntas e tomar pequenas iniciativas "
        "quando isso fizer sentido."
    )

    falar(
        "Você pode dizer sim, às vezes ou não."
    )

    return perguntar_opcao(
        "Como você prefere?",
        opcoes,
        "2",
    )


# ============================================================
# INTERRUPÇÃO
# ============================================================

def perguntar_interrupcao() -> bool:

    return perguntar_sim_nao(
        "Quando eu estiver falando, "
        "você quer poder me interromper falando por cima?"
    )


# ============================================================
# MEMÓRIA
# ============================================================

def perguntar_memoria() -> bool:

    return perguntar_sim_nao(
        "Você quer que eu memorize algumas informações "
        "sobre você para melhorar nossas conversas futuras?"
    )


def perguntar_tipo_memoria() -> str | None:

    falar(
        "Certo. Agora preciso saber quais informações "
        "você quer que eu possa guardar."
    )

    falar(
        "Pode escolher guardar tudo o que você pedir para eu guardar, "
        "guardar preferências e rotina, ou somente informações "
        "que você indicar diretamente."
    )

    opcoes = {
        "1": "tudo",
        "2": "preferencias e rotina",
        "3": "somente o que eu indicar",
    }

    resultado = perguntar_opcao(
        "Como você prefere?",
        opcoes,
        "1",
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
        "junto com o Windows?"
    )


# ============================================================
# SAUDAÇÃO
# ============================================================

def perguntar_saudacao() -> bool:

    return perguntar_sim_nao(
        "Quando eu iniciar, você quer que eu "
        "dê uma mensagem de boas-vindas?"
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

    falar(
        f"Essa e a {configuracao['nome']}. "
        "Veja se voce gosta desta voz."
    )


def escolher_voz() -> str:

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

    opcoes = {
        "1": "primeira",
        "2": "segunda",
        "3": "terceira",
    }

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

def executar_configuracao() -> bool:

    if configuracao_concluida():
        return False

    # ========================================================
    # APRESENTAÇÃO
    # ========================================================

    falar(
        "Olá! Eu sou a Yasm."
    )

    falar(
        "Sou uma assistente virtual desenvolvida como "
        "um projeto de tecnologia, criada para ajudar no "
        "uso do computador, facilitar tarefas, pesquisar "
        "informações e tornar a interação com o computador "
        "mais natural."
    )

    falar(
        "Fui criada por um estudante do ensino médio, "
        "como parte de um projeto pessoal de programação "
        "e desenvolvimento de inteligência artificial."
    )

    falar(
        "Meu desenvolvimento reúne programação, "
        "reconhecimento de voz, inteligência artificial, "
        "memória, síntese de voz e integração com recursos "
        "do computador."
    )

    falar(
        "Minhas capacidades continuam evoluindo à medida "
        "que novas ideias são implementadas, testadas "
        "e aprimoradas."
    )

    falar(
        "Isso significa que novos recursos podem surgir "
        "com o tempo e algumas das minhas funções também "
        "podem receber melhorias."
    )

    falar(
        "Mas antes de começarmos a trabalhar juntos, "
        "quero conhecer você um pouco melhor."
    )

    falar(
        "Vou fazer algumas perguntas para descobrir "
        "como você prefere que eu funcione."
    )

    falar(
        "Não precisa responder usando números. "
        "Pode falar normalmente, usando suas próprias palavras."
    )

    # ========================================================
    # IDENTIDADE
    # ========================================================

    nome_usuario = (
        perguntar_nome()
    )

    falar(
        f"Prazer em conhecer você, {nome_usuario}."
    )

    falar(
        "Agora quero saber como você gostaria "
        "de me chamar."
    )

    nome_assistente = (
        perguntar_nome_assistente()
    )

    falar(
        f"Perfeito. Então meu nome será "
        f"{nome_assistente}."
    )

    falar(
        "Agora vamos definir algumas características "
        "da forma como eu vou conversar com você."
    )

    # ========================================================
    # PERSONALIDADE
    # ========================================================

    personalidade = (
        perguntar_personalidade()
    )

    falar(
        "Entendi. Já estou começando a descobrir "
        "qual estilo combina mais com você."
    )

    # ========================================================
    # RESPOSTAS
    # ========================================================

    tamanho_respostas = (
        perguntar_tamanho_resposta()
    )

    falar(
        "Perfeito. Vou levar isso em consideração "
        "nas próximas conversas."
    )

    # ========================================================
    # PESQUISA
    # ========================================================

    pesquisa = (
        perguntar_pesquisa()
    )

    falar(
        "Certo. Agora já sei como você prefere "
        "que eu lide com informações que eu não conheço."
    )

    # ========================================================
    # CORRETOR
    # ========================================================

    corretor_ativo = (
        perguntar_corretor()
    )

    falar(
        "Entendido."
    )

    # ========================================================
    # INICIATIVA
    # ========================================================

    iniciativa = (
        perguntar_iniciativa()
    )

    falar(
        "Boa. Isso vai me ajudar a entender "
        "quanto devo participar espontaneamente "
        "das nossas conversas."
    )

    # ========================================================
    # INTERRUPÇÃO
    # ========================================================

    interrupcao = (
        perguntar_interrupcao()
    )

    falar(
        "Certo. Vamos para a próxima configuração."
    )

    # ========================================================
    # MEMÓRIA
    # ========================================================

    memoria_ativa = (
        perguntar_memoria()
    )

    memoria_tipo = None

    if memoria_ativa:

        memoria_tipo = (
            perguntar_tipo_memoria()
        )

        falar(
            "Entendi. Vou usar essa preferência "
            "como regra para minha memória."
        )

    # ========================================================
    # WINDOWS
    # ========================================================

    inicializar_windows = (
        perguntar_inicializacao()
    )

    # ========================================================
    # SAUDAÇÃO
    # ========================================================

    saudacao_inicio = (
        perguntar_saudacao()
    )

    # ========================================================
    # USO
    # ========================================================

    uso_principal = (
        perguntar_uso_principal()
    )

    falar(
        "Ótimo. Assim também consigo entender "
        "em que tipo de tarefa devo ser mais útil para você."
    )

    # ========================================================
    # NÍVEL
    # ========================================================

    nivel_tecnico = (
        perguntar_nivel_tecnico()
    )

    # ========================================================
    # VOZ
    # ========================================================

    voz_id = escolher_voz()

    # ========================================================
    # CONFIGURAÇÃO COMPLETA
    # ========================================================

    nova_configuracao = {

        "usuario": {
            "nome": nome_usuario,
        },

        "assistente": {
            "nome": nome_assistente,
        },

        "voz": {
            "id": voz_id,
        },

        "preferencias": {

            "personalidade": (
                personalidade
            ),

            "tamanho_respostas": (
                tamanho_respostas
            ),

            "pesquisa_automatica": {
                "1": True,
                "2": "perguntar",
                "3": False,
            }.get(
                pesquisa,
                True,
            ),

            "corretor_ativo": (
                corretor_ativo
            ),

            "iniciativa": {"1": "sim", "2": "as vezes", "3": "nao"}.get(iniciativa, "as vezes"),

            "interrupcao": (
                interrupcao
            ),

            "memoria_ativa": (
                memoria_ativa
            ),

            "tipo_memoria": (
                memoria_tipo
            ),

            "inicializar_windows": (
                inicializar_windows
            ),

            "saudacao_inicio": (
                saudacao_inicio
            ),

            "uso_principal": (
                uso_principal
            ),

            "nivel_tecnico": (
                nivel_tecnico
            ),
        },

        "configuracao": {
            "concluida": True,
        },
    }

    # ========================================================
    # SALVAR SEM APAGAR OUTRAS INFORMAÇÕES
    # ========================================================

    for chave, valor in nova_configuracao.items():

        if isinstance(
            valor,
            dict,
        ):

            memoria.setdefault(
                chave,
                {}
            ).update(
                valor
            )

        else:

            memoria[
                chave
            ] = valor

    # ========================================================
    # SALVA
    # ========================================================

    salvar_memoria(
        memoria
    )

    # ========================================================
    # FINAL
    # ========================================================

    falar(
        f"Pronto, {nome_usuario}. "
        "Minha configuração foi concluída."
    )

    falar(
        "Agora eu já sei como chamar você, "
        "como você prefere conversar comigo "
        "e como devo agir em diferentes situações."
    )

    falar(
        resumo_configuracao(
            nova_configuracao
        )
    )

    falar(
        f"Tudo certo, {nome_usuario}. "
        "A partir de agora, vou seguir as preferências "
        "que você definiu para mim."
    )

    falar(
        "Quando precisar de mim, é só me chamar."
    )

    return True


# ============================================================
# API
# ============================================================

def precisa_configurar() -> bool:

    return not configuracao_concluida()


def iniciar() -> bool:

    return executar_configuracao()


# ============================================================
# TESTE DIRETO
# ============================================================

if __name__ == "__main__":

    executar_configuracao()
