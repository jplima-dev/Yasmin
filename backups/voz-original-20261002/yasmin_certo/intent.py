"""
intent.py
Sistema central de intencoes da Yasm.

Responsabilidades:

- normalizacao;
- aliases;
- detector da palavra Yasm;
- catalogo de intencoes;
- classificacao;
- confianca;
- extracao de aplicativos;
- integracao com o corretor de transcricao;
- fallback automatico para pesquisa.
"""

from __future__ import annotations

import re
import unicodedata

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Iterable


# ============================================================
# CORRETOR
# ============================================================

try:

    from servicos.corretor import (
        corrigir as corrigir_transcricao,
    )

except ImportError:

    corrigir_transcricao = None


# ============================================================
# CONFIGURACAO
# ============================================================

LIMIAR_EXECUCAO = 0.75

LIMIAR_PESQUISA = 0.55

MINIMO_SIMILARIDADE = 0.55


# ============================================================
# MODELO DE INTENCAO
# ============================================================

@dataclass
class Intent:

    nome: str

    confianca: float

    parametros: dict[str, Any] = field(
        default_factory=dict
    )

    texto_original: str = ""

    texto_normalizado: str = ""

    texto_corrigido: str = ""

    corretor_usado: bool = False

    confianca_correcao: float = 0.0

    @property
    def aceita(self) -> bool:

        return (
            self.confianca
            >= LIMIAR_EXECUCAO
        )


# ============================================================
# NOMES DA YASM
# ============================================================

VARIACOES_YASM = {

    "yasm",

    "yas",

    "yasmin",

    "yasmim",

    "yasmine",

    "yasma",

    "iasmin",

    "iasmim",

    "jasmin",

    "jasm",

    "yaz",

    "yazmin",

    "yazmim",
}


# ============================================================
# NORMALIZACAO
# ============================================================

def normalizar(texto: str) -> str:

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
        r"[^\w\s-]",
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
# DETECCAO DA YASM
# ============================================================

def parece_yasm(
    palavra: str,
) -> bool:

    palavra = normalizar(
        palavra
    )

    if not palavra:

        return False

    if palavra in VARIACOES_YASM:

        return True

    return (
        SequenceMatcher(
            None,
            palavra,
            "yasm",
        ).ratio()
        >= 0.65
    )


def chamou_yasm(
    texto: str,
) -> bool:

    texto_n = normalizar(
        texto
    )

    return any(
        parece_yasm(
            palavra
        )
        for palavra in texto_n.split()
    )


def remover_chamada(
    texto: str,
) -> str:

    texto = normalizar(
        texto
    )

    partes = texto.split()

    while (
        partes
        and parece_yasm(
            partes[0]
        )
    ):

        partes.pop(0)

    return " ".join(
        partes
    ).strip()


def texto_contem(
    texto: str,
    termo: str,
) -> bool:

    texto = normalizar(
        texto
    )

    termo = normalizar(
        termo
    )

    if not texto or not termo:

        return False

    return re.search(
        r"(?<!\w)"
        + re.escape(termo)
        + r"(?!\w)",
        texto,
    ) is not None


# ============================================================
# NORMALIZACAO DE APLICATIVOS
# ============================================================

APLICATIVOS_CONHECIDOS = {

    "vscode": (
        "vscode",
        "vs code",
        "v s code",
        "visual studio code",
        "visual studio",
    ),

    "opera": (
        "opera",
        "opera browser",
    ),

    "chrome": (
        "chrome",
        "google chrome",
        "navegador chrome",
    ),

    "edge": (
        "edge",
        "microsoft edge",
        "navegador edge",
    ),

    "firefox": (
        "firefox",
        "mozilla firefox",
        "navegador firefox",
    ),

    "intellij": (
        "intellij",
        "intelij",
        "inteli j",
        "intellij idea",
    ),

    "pycharm": (
        "pycharm",
        "pie charm",
        "jetbrains pycharm",
    ),

    "python idle": (
        "idle",
        "python idle",
        "idle python",
    ),

    "mysql workbench": (
        "mysql workbench",
        "my sql workbench",
        "my sequel workbench",
    ),

    "servidor champ": (
        "servidor champ",
        "servidor xamp",
        "xampp",
        "xamp",
        "xampp server",
        "xamp server",
    ),

    "explorador": (
        "explorador",
        "explorer",
        "arquivos",
        "explorador de arquivos",
    ),

    "bloco de notas": (
        "bloco de notas",
        "notepad",
        "notas",
    ),

    "calculadora": (
        "calculadora",
        "calc",
    ),

    "paint": (
        "paint",
        "mspaint",
    ),

    "prompt": (
        "cmd",
        "prompt",
        "terminal",
        "prompt de comando",
    ),

    "powershell": (
        "powershell",
        "power shell",
    ),

    "terminal windows": (
        "terminal windows",
        "windows terminal",
        "terminal do windows",
        "wt",
    ),

    "gerenciador de tarefas": (
        "gerenciador de tarefas",
        "task manager",
    ),

    "steam": (
        "steam",
        "steam da valve",
    ),

    "discord": (
        "discord",
    ),

    "spotify": (
        "spotify",
    ),

    "word": (
        "word",
        "microsoft word",
    ),

    "excel": (
        "excel",
        "microsoft excel",
    ),

    "powerpoint": (
        "powerpoint",
        "power point",
        "microsoft powerpoint",
    ),

    "configuracoes": (
        "configuracoes",
        "configuracao",
        "settings",
        "configuracoes do windows",
    ),
}


def normalizar_aplicativo(
    texto: str,
) -> str:

    texto = normalizar(
        texto
    )

    for nome, aliases in (
        APLICATIVOS_CONHECIDOS.items()
    ):

        for alias in aliases:

            if (
                texto
                == normalizar(alias)
            ):

                return nome

    return texto


def identificar_aplicativo(
    texto: str,
) -> str | None:

    texto = normalizar(
        texto
    )

    encontrados: list[
        tuple[int, str]
    ] = []

    for nome, aliases in (
        APLICATIVOS_CONHECIDOS.items()
    ):

        for alias in aliases:

            alias_n = normalizar(
                alias
            )

            if (
                alias_n
                and texto_contem(
                    texto,
                    alias_n,
                )
            ):

                encontrados.append(
                    (
                        len(alias_n),
                        nome,
                    )
                )

    if not encontrados:

        return None

    encontrados.sort(
        reverse=True
    )

    return encontrados[0][1]


# ============================================================
# REGISTRO DE INTENCOES
# ============================================================

INTENCOES = {

    "HORA": {

        "frases": (
            "que horas sao",
            "que hora e",
            "qual a hora",
            "qual e a hora",
            "qual o horario",
            "qual e o horario",
            "me diga a hora",
            "me fala a hora",
            "me diga que horas sao",
            "me fala que horas sao",
            "horas agora",
            "horario agora",
            "ver a hora",
        ),

        "palavras": (
            "hora",
            "horas",
            "horario",
        ),
    },

    "DATA": {

        "frases": (
            "que dia e hoje",
            "qual a data",
            "qual e a data",
            "me diga a data",
            "me fala a data",
            "qual o dia de hoje",
            "que dia estamos",
            "data de hoje",
        ),

        "palavras": (
            "data",
            "hoje",
        ),
    },

    "ENCERRAR": {

        "frases": (
            "tchau",
            "ate logo",
            "ate mais",
            "ate depois",
            "ate amanha",
            "adeus",
            "pode encerrar",
            "pode desligar",
            "desligar",
            "fechar yasm",
            "encerrar yasm",
            "desligar yasm",
            "vai dormir",
            "fique quieta",
            "fica quieta",
        ),

        "palavras": (
            "tchau",
            "chau",
            "xau",
            "falou",
            "flw",
            "adeus",
            "encerrar",
            "encerra",
            "desligar",
            "desliga",
            "desligue",
            "parar",
            "pare",
        ),
    },

    "SAUDACAO": {

        "frases": (
            "oi",
            "ola",
            "e ai",
            "eai",
            "opa",
            "hey",
            "hello",
            "bom dia",
            "boa tarde",
            "boa noite",
        ),

        "palavras": (
            "oi",
            "ola",
            "opa",
            "hey",
            "hello",
        ),
    },

    "IDENTIDADE": {

        "frases": (
            "quem e voce",
            "o que e voce",
            "quem e a yasm",
            "quem e yasmin",
            "qual e seu nome",
            "como voce se chama",
            "o que voce e",
        ),

        "palavras": (
            "nome",
        ),
    },

    "COMO_ESTOU": {

        "frases": (
            "voce esta bem",
            "como voce esta",
            "como voce ta",
            "tudo bem com voce",
            "ta tudo bem",
            "como voce se sente",
            "voce esta legal",
        ),

        "palavras": (
            "bem",
        ),
    },

    "AGRADECIMENTO": {

        "frases": (
            "obrigado",
            "obrigada",
            "valeu",
            "muito obrigado",
            "muito obrigada",
            "brigado",
            "brigada",
        ),

        "palavras": (
            "obrigado",
            "obrigada",
            "valeu",
        ),
    },

    "ABRIR_APLICATIVO": {

        "frases": (
            "abrir",
            "abra",
            "abre",
            "iniciar",
            "inicia",
            "executar",
            "execute",
            "rodar",
            "rode",
            "ligar",
            "liga",
        ),

        "palavras": (),
    },

    "FECHAR_APLICATIVO": {

        "frases": (
            "fechar",
            "fecha",
            "feche",
            "encerrar",
            "encerra",
            "sair do",
            "fechar o",
            "fechar a",
        ),

        "palavras": (),
    },

    "ATALHO_JAVA": {

        "frases": (
            "programar java",
            "programacao java",
            "ambiente java",
            "desenvolvimento java",
            "java desenvolvimento",
        ),

        "palavras": (
            "java",
        ),
    },

    "ATALHO_PROGRAMAR": {

        "frases": (
            "programar",
            "ir programar",
            "modo programacao",
            "ambiente de programacao",
        ),

        "palavras": (
            "programar",
        ),
    },

    "ATALHO_BANCO": {

        "frases": (
            "bd",
            "banco de dados",
            "banco de dado",
            "ambiente de banco",
            "ambiente banco",
            "programar banco",
            "programar banco de dados",
        ),

        "palavras": (
            "bd",
            "banco",
        ),
    },

    "MUSICA": {

        "frases": (
            "tocar musica",
            "poe musica",
            "poe uma musica",
            "poe a musica",
            "coloca musica",
            "coloca uma musica",
            "coloca a musica",
            "toque uma musica",
            "coloque uma musica",
            "coloca uma musica",
            "quero ouvir musica",
            "tocar uma musica",
            "proxima musica",
            "pausar musica",
            "pause a musica",
            "parar musica",
        ),

        "palavras": (
            "musica",
            "musicas",
            "music",
            "song",
            "songs",
            "play",
            "pause",
        ),
    },

    "MEMORIA": {

        "frases": (
            "lembre que",
            "lembra que",
            "anote que",
            "guarde que",
            "salve que",
            "o que voce lembra",
            "o que voce sabe sobre mim",
            "quais sao minhas memorias",
            "esqueca isso",
        ),

        "palavras": (
            "memoria",
            "lembrar",
            "lembre",
            "esqueca",
        ),
    },

    "TAREFAS": {

        "frases": (
            "minhas tarefas",
            "listar tarefas",
            "tarefas pendentes",
            "quais sao minhas tarefas",
            "adicione tarefa",
            "crie tarefa",
            "nova tarefa",
            "concluir tarefa",
            "marcar tarefa",
        ),

        "palavras": (
            "tarefa",
            "tarefas",
        ),
    },

    "TIMER": {

        "frases": (
            "coloque um timer",
            "crie um timer",
            "inicie um timer",
            "marque um timer",
            "me avise em",
            "me lembra em",
        ),

        "palavras": (
            "timer",
            "temporizador",
        ),
    },

    "VOLUME": {

        "frases": (
            "aumente o volume",
            "abaixe o volume",
            "diminua o volume",
            "aumenta o som",
            "abaixa o som",
            "mais volume",
            "menos volume",
            "mute",
            "silenciar",
        ),

        "palavras": (
            "volume",
            "som",
            "silenciar",
            "mute",
        ),
    },

    "PESQUISA": {

        "frases": (
            "pesquise",
            "pesquisa para mim",
            "pesquisar para mim",
            "procure para mim",
            "procura para mim",
            "busque para mim",
            "busca para mim",
            "me diga sobre",
            "me fale sobre",
            "quero saber sobre",
            "o que aconteceu",
        ),

        "palavras": (
            "pesquisa",
            "pesquise",
            "pesquisar",
            "procure",
            "procurar",
            "busca",
            "buscar",
        ),
    },

    "ESTUDO": {

        "frases": (
            "vamos estudar",
            "quero estudar",
            "me ensina python",
            "me ensina java",
            "quero aprender python",
            "quero aprender java",
            "me passe um exercicio",
            "me passa um exercicio",
            "vamos fazer um quiz",
        ),

        "palavras": (
            "estudar",
            "estudo",
            "exercicio",
            "quiz",
            "aprender",
        ),
    },
}


GATILHOS_ABRIR = (
    "abrir",
    "abra",
    "abre",
    "iniciar",
    "inicia",
    "executar",
    "execute",
    "rodar",
    "rode",
    "ligar",
    "liga",
)


GATILHOS_FECHAR = (
    "fechar",
    "fecha",
    "feche",
    "encerrar",
    "encerra",
    "sair do",
    "fechar o",
    "fechar a",
)


# ============================================================
# NORMALIZACAO DA FRASE DO CORRETOR
# ============================================================

def _corrigir_transcricao(
    texto: str,
    contexto: Iterable[str] | None = None,
) -> tuple[str, bool, float, str, list[str]]:

    if corrigir_transcricao is None:

        return (
            texto,
            False,
            0.0,
            "corretor_indisponivel",
            [],
        )

    try:

        resultado = corrigir_transcricao(
            texto,
            contexto=contexto,
            intencoes=(
                {
                    nome: dados["frases"]
                    for nome, dados
                    in INTENCOES.items()
                }
            ),
        )

    except Exception:

        return (
            texto,
            False,
            0.0,
            "erro_corretor",
            [],
        )

    texto_corrigido = str(
        resultado.corrigido or texto
    ).strip()

    confianca = float(
        resultado.confianca or 0.0
    )

    alterado = bool(
        resultado.alterado
    )

    metodo = str(
        resultado.metodo or ""
    )

    detalhes = list(
        resultado.detalhes or []
    )

    # --------------------------------------------------------
    # Não aceitamos correções muito fracas.
    # --------------------------------------------------------

    if (
        not texto_corrigido
        or confianca < 0.78
    ):

        return (
            texto,
            False,
            confianca,
            metodo,
            detalhes,
        )

    return (
        texto_corrigido,
        alterado,
        confianca,
        metodo,
        detalhes,
    )


# ============================================================
# PONTUACAO
# ============================================================

def _pontuar(
    texto: str,
    frases: tuple[str, ...],
    palavras_chave: tuple[str, ...],
) -> float:

    texto_n = normalizar(
        texto
    )

    melhor = 0.0

    for frase in frases:

        frase_n = normalizar(
            frase
        )

        if not frase_n:
            continue

        # ----------------------------------------------------
        # Correspondência exata
        # ----------------------------------------------------

        if texto_n == frase_n:

            melhor = max(
                melhor,
                1.0,
            )

        # ----------------------------------------------------
        # Frase contida
        # ----------------------------------------------------

        elif texto_contem(
            texto_n,
            frase_n,
        ):

            melhor = max(
                melhor,
                0.92,
            )

        # ----------------------------------------------------
        # Similaridade
        # ----------------------------------------------------

        else:

            similaridade = (
                SequenceMatcher(
                    None,
                    texto_n,
                    frase_n,
                ).ratio()
            )

            if similaridade >= 0.90:

                melhor = max(
                    melhor,
                    0.86,
                )

            elif similaridade >= 0.78:

                melhor = max(
                    melhor,
                    0.72,
                )

            elif similaridade >= MINIMO_SIMILARIDADE:

                melhor = max(
                    melhor,
                    0.58,
                )

    # --------------------------------------------------------
    # Palavras-chave
    # --------------------------------------------------------

    for palavra in palavras_chave:

        if texto_contem(
            texto_n,
            palavra,
        ):

            melhor = max(
                melhor,
                0.62,
            )

    return min(
        melhor,
        1.0,
    )


# ============================================================
# REGRAS DE PRIORIDADE
# ============================================================

def _ajustar(
    nome: str,
    confianca: float,
    texto: str,
) -> tuple[
    str,
    float,
    dict[str, Any],
]:

    texto_n = normalizar(
        texto
    )

    # --------------------------------------------------------
    # Encerramento
    # --------------------------------------------------------

    for frase in (
        INTENCOES[
            "ENCERRAR"
        ][
            "frases"
        ]
    ):

        if (
            texto_n == frase
            or texto_contem(
                texto_n,
                frase,
            )
        ):

            return (
                "ENCERRAR",
                1.0,
                {},
            )

    # --------------------------------------------------------
    # Pesquisa explícita
    # --------------------------------------------------------

    for gatilho in (
        "pesquisa para mim",
        "pesquise",
        "pesquisa",
        "pesquisar",
        "procure para mim",
        "procura para mim",
        "busque para mim",
        "busca para mim",
    ):

        if texto_contem(
            texto_n,
            gatilho,
        ):

            return (
                "PESQUISA",
                1.0,
                {
                    "consulta": texto_n,
                    "origem": "explicita",
                },
            )

    # --------------------------------------------------------
    # Aplicativo
    # --------------------------------------------------------

    aplicativo = identificar_aplicativo(
        texto_n
    )

    if aplicativo:

        if any(
            texto_contem(
                texto_n,
                gatilho,
            )
            for gatilho in GATILHOS_FECHAR
        ):

            return (
                "FECHAR_APLICATIVO",
                0.99,
                {
                    "aplicativo": aplicativo,
                },
            )

        if any(
            texto_contem(
                texto_n,
                gatilho,
            )
            for gatilho in GATILHOS_ABRIR
        ):

            return (
                "ABRIR_APLICATIVO",
                0.99,
                {
                    "aplicativo": aplicativo,
                },
            )

        # ----------------------------------------------------
        # Somente o nome do aplicativo
        # ----------------------------------------------------

        for alias in (
            APLICATIVOS_CONHECIDOS.get(
                aplicativo,
                (),
            )
        ):

            if texto_n == normalizar(alias):

                return (
                    "ABRIR_APLICATIVO",
                    0.95,
                    {
                        "aplicativo": aplicativo,
                    },
                )

    # --------------------------------------------------------
    # Java
    # --------------------------------------------------------

    if (
        "java" in texto_n
        and "programar" in texto_n
    ):

        return (
            "ATALHO_JAVA",
            0.99,
            {},
        )

    # --------------------------------------------------------
    # Banco de dados
    # --------------------------------------------------------

    if (
        texto_n == "bd"
        or (
            "banco" in texto_n
            and "dados" in texto_n
        )
    ):

        return (
            "ATALHO_BANCO",
            0.99,
            {},
        )

    # --------------------------------------------------------
    # Programar
    # --------------------------------------------------------

    if texto_n in (
        "programar",
        "ir programar",
        "modo programacao",
        "ambiente de programacao",
    ):

        return (
            "ATALHO_PROGRAMAR",
            0.98,
            {},
        )

    return (
        nome,
        confianca,
        {},
    )


# ============================================================
# CLASSIFICAR
# ============================================================

def classificar(
    texto: str,
    contexto: Iterable[str] | None = None,
    usar_corretor: bool = True,
) -> Intent:

    original = str(
        texto or ""
    )

    texto_normalizado_original = normalizar(
        original
    )

    # Comandos conhecidos devem chegar intactos ao executor. O corretor
    # generico pode transformar numeros, nomes de tarefas e perguntas locais.
    comando = remover_chamada(texto_normalizado_original)
    locais = (
        ("CALCULO", r"\b(?:calcule|calcular|quanto e)\b"),
        ("CLIMA", r"\b(?:clima|temperatura)\b"),
        ("AJUDA", r"^(?:ajuda|comandos|o que voce faz|o que voce consegue)$"),
        ("STATUS", r"^(?:status|relatorio|diagnostico)(?: do sistema)?$"),
        ("HORA", r"^(?:hora|horas|horario|que horas sao|qual e a hora|qual a hora|hora agora)$"),
        ("DATA", r"^(?:data|qual (?:e )?a data|que dia e hoje|qual o dia de hoje)(?: de hoje)?$"),
        ("IDENTIDADE", r"^(?:quem e voce|o que e voce|o que voce e|qual (?:e )?seu nome|como voce se chama)$"),
        ("NOME_USUARIO", r"^(?:qual (?:e )?(?:o )?meu nome|quem sou eu)$"),
        ("TAREFAS", r"^(?:minhas tarefas|listar tarefas|tarefas pendentes|quais sao minhas tarefas|adicione tarefa|crie tarefa|nova tarefa|anote tarefa|concluir tarefa|marcar tarefa|terminei|conclui)\b"),
        ("MEMORIA", r"^(?:lembre que|lembra que|anote que|guarde que|salve que|memorize que|minhas notas|apagar notas|limpar memoria|apague minhas notas|o que voce lembra|o que voce sabe sobre mim)\b"),
        ("ALTERAR_NOME", r"^(?:meu nome e|me chamo|pode me chamar de)\b"),
        ("TIMER", r"\b(?:timer|temporizador|pomodoro)\b"),
        ("AUDIO", r"^(?:calibrar microfone|recalibrar)\b"),
        ("ESTUDO", r"^(?:me explique|explique|me ensine|me ensina|explicar|exercicio|crie um exercicio|quiz|iniciar quiz|plano de estudo|meu progresso|progresso|mostrar solucao|mostre a solucao|estudei)\b"),
        ("SITE", r"^(?:abrir|abra|abre) (?:o |a )?(?:google|youtube|gmail|github|whatsapp|documentacao python|python docs|pypi|stack overflow)\b"),
        ("RESULTADO_PESQUISA", r"^(?:abrir|abra|abre) (?:o )?(?:resultado|primeiro resultado|segundo resultado|terceiro resultado)\b"),
    )
    # Pesquisa explicitamente pedida tem prioridade sobre palavras de seu tema.
    pesquisa_explicita = re.match(
        r"^(?:pesquise|pesquisa|pesquisar|procure|procura|busque|busca|buscar)\b", comando
    )
    if not pesquisa_explicita:
        # Notas e tarefas podem citar calculos, clima ou outros comandos.
        locais = sorted(locais, key=lambda item: item[0] not in {"MEMORIA", "TAREFAS"})
        for nome_local, padrao in locais:
            if re.search(padrao, comando):
                return Intent(nome=nome_local, confianca=1.0, texto_original=original,
                              texto_normalizado=comando, texto_corrigido=comando)

    if not texto_normalizado_original:

        return Intent(
            nome="CHAMADA_CURTA",
            confianca=1.0,
            texto_original=original,
            texto_normalizado="",
            texto_corrigido="",
            corretor_usado=False,
            confianca_correcao=0.0,
        )

    # ========================================================
    # CORRETOR
    # ========================================================

    texto_corrigido = (
        texto_normalizado_original
    )

    corretor_usado = False

    confianca_correcao = 0.0

    metodo_correcao = ""

    detalhes_correcao = []

    if usar_corretor:

        (
            candidato,
            alterado,
            confianca,
            metodo,
            detalhes,
        ) = _corrigir_transcricao(
            original,
            contexto=contexto,
        )

        if (
            candidato
            and confianca >= 0.78
        ):

            texto_corrigido = normalizar(
                candidato
            )

            corretor_usado = alterado

            confianca_correcao = (
                confianca
            )

            metodo_correcao = (
                metodo
            )

            detalhes_correcao = (
                detalhes
            )

    # ========================================================
    # REMOVER CHAMADA
    # ========================================================

    texto_n = remover_chamada(
        texto_corrigido
    )

    # Se o corretor tiver transformado a chamada em algo
    # útil, trabalhamos com a versão corrigida.

    if not texto_n:

        return Intent(
            nome="CHAMADA_CURTA",
            confianca=1.0,
            texto_original=original,
            texto_normalizado="",
            texto_corrigido=texto_corrigido,
            corretor_usado=corretor_usado,
            confianca_correcao=confianca_correcao,
        )

    # ========================================================
    # RESULTADOS
    # ========================================================

    resultados: list[
        tuple[float, str]
    ] = []

    for nome, dados in (
        INTENCOES.items()
    ):

        confianca = _pontuar(
            texto_n,
            tuple(
                dados.get(
                    "frases",
                    (),
                )
            ),
            tuple(
                dados.get(
                    "palavras",
                    (),
                )
            ),
        )

        if confianca > 0:

            resultados.append(
                (
                    confianca,
                    nome,
                )
            )

    # ========================================================
    # NENHUMA INTENÇÃO
    # ========================================================

    if not resultados:

        return Intent(
            nome="DESCONHECIDA",
            confianca=0.0,
            texto_original=original,
            texto_normalizado=texto_n,
            texto_corrigido=texto_corrigido,
            corretor_usado=corretor_usado,
            confianca_correcao=confianca_correcao,
        )

    # ========================================================
    # MELHOR RESULTADO
    # ========================================================

    resultados.sort(
        reverse=True
    )

    melhor_confianca, melhor_nome = (
        resultados[0]
    )

    # ========================================================
    # REGRAS DE PRIORIDADE
    # ========================================================

    (
        melhor_nome,
        melhor_confianca,
        parametros,
    ) = _ajustar(
        melhor_nome,
        melhor_confianca,
        texto_n,
    )

    # ========================================================
    # CONFIANÇA MÍNIMA
    # ========================================================

    if melhor_confianca < LIMIAR_PESQUISA:

        return Intent(
            nome="DESCONHECIDA",
            confianca=melhor_confianca,
            texto_original=original,
            texto_normalizado=texto_n,
            texto_corrigido=texto_corrigido,
            corretor_usado=corretor_usado,
            confianca_correcao=confianca_correcao,
            parametros={
                "corretor_metodo": metodo_correcao,
                "corretor_detalhes": detalhes_correcao,
            },
        )

    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    return Intent(
        nome=melhor_nome,
        confianca=min(
            melhor_confianca,
            1.0,
        ),
        parametros={
            **parametros,

            "corretor_metodo": (
                metodo_correcao
            ),

            "corretor_detalhes": (
                detalhes_correcao
            ),
        },
        texto_original=original,
        texto_normalizado=texto_n,
        texto_corrigido=texto_corrigido,
        corretor_usado=corretor_usado,
        confianca_correcao=confianca_correcao,
    )


# ============================================================
# FALLBACK PARA PESQUISA
# ============================================================

def transformar_em_pesquisa(
    intent: Intent,
) -> Intent:

    if intent.nome == "PESQUISA":

        return intent

    consulta = (
        intent.texto_corrigido
        or intent.texto_original
        or intent.texto_normalizado
    )

    return Intent(
        nome="PESQUISA",
        confianca=1.0,
        parametros={
            "consulta": consulta,
            "origem": "fallback",
            "intencao_anterior": intent.nome,
        },
        texto_original=intent.texto_original,
        texto_normalizado=intent.texto_normalizado,
        texto_corrigido=intent.texto_corrigido,
        corretor_usado=intent.corretor_usado,
        confianca_correcao=intent.confianca_correcao,
    )


def precisa_pesquisar(
    intent: Intent,
) -> bool:

    return (
        intent.nome == "DESCONHECIDA"
        or intent.nome == "PESQUISA"
        or not intent.aceita
    )


def interpretar(
    texto: str,
    contexto: Iterable[str] | None = None,
    fallback_pesquisa: bool = True,
) -> Intent:

    resultado = classificar(
        texto,
        contexto=contexto,
        usar_corretor=True,
    )

    if (
        fallback_pesquisa
        and resultado.nome == "DESCONHECIDA"
    ):

        return transformar_em_pesquisa(
            resultado
        )

    return resultado


# ============================================================
# COMPATIBILIDADE
# ============================================================

def identificar_intencao(
    texto: str,
) -> str:

    return classificar(
        texto
    ).nome


def eh_pesquisa(
    texto: str,
) -> bool:

    return (
        classificar(
            texto
        ).nome
        == "PESQUISA"
    )


# ============================================================
# FUNÇÃO DE CORREÇÃO EXTERNA
# ============================================================

def corrigir_texto(
    texto: str,
    contexto: Iterable[str] | None = None,
) -> str:

    resultado = _corrigir_transcricao(
        texto,
        contexto=contexto,
    )

    return normalizar(
        resultado[0]
    )


# ============================================================
# DEBUG / DIAGNÓSTICO
# ============================================================

def explicar(
    texto: str,
) -> dict[str, Any]:

    resultado = interpretar(
        texto,
        fallback_pesquisa=False,
    )

    return {

        "texto_original": (
            resultado.texto_original
        ),

        "texto_normalizado": (
            resultado.texto_normalizado
        ),

        "texto_corrigido": (
            resultado.texto_corrigido
        ),

        "intencao": (
            resultado.nome
        ),

        "confianca": round(
            resultado.confianca,
            3,
        ),

        "aceita": (
            resultado.aceita
        ),

        "parametros": (
            resultado.parametros
        ),

        "corretor_usado": (
            resultado.corretor_usado
        ),

        "confianca_correcao": round(
            resultado.confianca_correcao,
            3,
        ),

        "precisa_pesquisar": (
            precisa_pesquisar(
                resultado
            )
        ),
    }


# ============================================================
# TESTES
# ============================================================

if __name__ == "__main__":

    testes = (

        "Yasmin, que horas sao?",

        "Yasmin, que oras sao?",

        "Yasmin, tchau",

        "Yasmin, tchao",

        "tchau Yasmin",

        "Yasmin tchau",

        "Yasmin, abre o VS Code",

        "Yasmin, abre o v s code",

        "Yasmin, fecha o Opera",

        "Yasmin, programar Java",

        "Yasmin, BD",

        "Yasmin, quem ganhou a Copa de 2010?",

        "Yasmin, qual a populacao do Japao?",

        "Yasmin, voce esta bem?",

        "Yasmin, quem e voce?",

        "Yasmin, obrigado",

        "Yasmin, uma coisa que voce nao sabe",

        "Yasmin, valeu",

        "Yasmin, falow",

    )

    print(
        "=" * 72
    )

    print(
        "TESTE DO SISTEMA DE INTENCOES + CORRETOR"
    )

    print(
        "=" * 72
    )

    for texto in testes:

        print()

        print(
            f"Entrada: {texto}"
        )

        resultado = explicar(
            texto
        )

        print(
            "Normalizado:",
            resultado[
                "texto_normalizado"
            ]
        )

        print(
            "Corrigido:",
            resultado[
                "texto_corrigido"
            ]
        )

        print(
            "Intencao:",
            resultado[
                "intencao"
            ]
        )

        print(
            f"Confianca: "
            f"{resultado['confianca']:.3f}"
        )

        print(
            "Corretor:",
            resultado[
                "corretor_usado"
            ]
        )

        print(
            f"Confianca correcao: "
            f"{resultado['confianca_correcao']:.3f}"
        )

        print(
            "Pesquisa:",
            resultado[
                "precisa_pesquisar"
            ]
        )

        if resultado[
            "parametros"
        ]:

            print(
                "Parametros:",
                resultado[
                    "parametros"
                ]
            )
