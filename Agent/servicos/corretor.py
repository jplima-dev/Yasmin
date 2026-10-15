from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable


# ============================================================
# CONFIGURAÇÃO
# ============================================================

LIMIAR_CORRECAO_ALTA = 0.90
LIMIAR_CORRECAO_MEDIA = 0.78
LIMIAR_CORRECAO_BAIXA = 0.68

TAMANHO_MAXIMO_CONTEXT0 = 8

MAXIMO_PALAVRAS_DIFERENTES = 4


# ============================================================
# RESULTADO
# ============================================================

@dataclass
class ResultadoCorrecao:
    original: str
    corrigido: str
    confianca: float
    alterado: bool
    metodo: str
    detalhes: list[str] = field(default_factory=list)

    @property
    def aceito(self) -> bool:
        return self.confianca >= LIMIAR_CORRECAO_BAIXA


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def normalizar(texto: str) -> str:
    """
    Normaliza texto para comparação.

    Remove:
    - acentos;
    - pontuação;
    - espaços duplicados;
    - diferenças de maiúsculas/minúsculas.
    """

    texto = str(texto or "").strip().lower()

    texto = unicodedata.normalize(
        "NFD",
        texto,
    )

    texto = "".join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != "Mn"
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
# ALIASES FIXOS
# ============================================================
#
# Primeira camada:
# correções claramente conhecidas.
#
# Exemplo:
#
#   "tchao" -> "tchau"
#   "yasmin" -> "yasmin"
#   "ve es code" -> "vscode"
#

ALIASES = {

    # --------------------------------------------------------
    # YASM
    # --------------------------------------------------------

    "yasmin": (
        "yasmin",
        "yasmim",
        "yasmine",
        "iasmin",
        "iasmim",
        "yasma",
        "jasmine",
        "jasmin",
        "jasm",
        "yazmin",
        "yazmim",
        "yas",
        "yasm",
        "yaz",
    ),

    # --------------------------------------------------------
    # DESPEDIDAS
    # --------------------------------------------------------

    "tchau": (
        "tchau",
        "tchao",
        "tchauu",
        "tchou",
        "txau",
        "chau",
        "xau",
        "xauxau",
        "xau xau",
    ),

    "falou": (
        "falou",
        "falô",
        "faloo",
        "falouu",
    ),

    "valeu": (
        "valeu",
        "valeu",
        "valew",
        "valeuu",
        "vlw",
    ),

    # --------------------------------------------------------
    # APLICATIVOS
    # --------------------------------------------------------

    "vscode": (
        "vscode",
        "vs code",
        "v s code",
        "v es code",
        "vscodee",
        "visual studio code",
        "visual studio",
    ),

    "intellij": (
        "intellij",
        "intelij",
        "inteli",
        "inteli j",
        "intellij idea",
        "intelij idea",
    ),

    "mysql workbench": (
        "mysql workbench",
        "my sql workbench",
        "my sequel workbench",
        "mysql wordbench",
        "mysql work benche",
    ),

    "xampp": (
        "xampp",
        "xamp",
        "xanp",
        "xamp server",
        "xampp server",
        "servidor xampp",
        "servidor xamp",
    ),

    "opera": (
        "opera",
        "operah",
        "opera browser",
    ),

    # --------------------------------------------------------
    # TERMOS DE PROGRAMAÇÃO
    # --------------------------------------------------------

    "python": (
        "python",
        "paiton",
        "piton",
        "paiton",
        "pyton",
    ),

    "javascript": (
        "javascript",
        "java script",
        "javaescript",
        "javascript",
        "javascrip",
    ),

    "typescript": (
        "typescript",
        "type script",
        "tip script",
        "typescrip",
    ),

    "java": (
        "java",
        "javar",
        "javaa",
    ),

    "sql": (
        "sql",
        "sequel",
        "esquel",
        "sql",
    ),

    # --------------------------------------------------------
    # TERMOS DE SISTEMA
    # --------------------------------------------------------

    "microfone": (
        "microfone",
        "micro fone",
        "microfonee",
        "microfoni",
    ),

    "internet": (
        "internet",
        "inter net",
        "interenete",
        "internete",
    ),

    "computador": (
        "computador",
        "computado",
        "computadoor",
    ),

    "navegador": (
        "navegador",
        "navegador",
        "navegador web",
    ),

    # --------------------------------------------------------
    # PESQUISA
    # --------------------------------------------------------

    "pesquisa": (
        "pesquisa",
        "pesquiza",
        "pesquiza",
        "pesquizar",
        "pesquisar",
        "pesquise",
    ),

    "procurar": (
        "procurar",
        "procura",
        "procure",
        "procurra",
    ),

    # --------------------------------------------------------
    # HORÁRIO
    # --------------------------------------------------------

    "horas": (
        "horas",
        "oras",
        "hora",
    ),

    "horario": (
        "horario",
        "horário",
        "orario",
        "horarios",
    ),

    # --------------------------------------------------------
    # OUTROS
    # --------------------------------------------------------

    "obrigado": (
        "obrigado",
        "obrigada",
        "obrigadu",
        "obg",
        "brigado",
        "brigada",
    ),
}


# ============================================================
# ÍNDICE REVERSO
# ============================================================

ALIAS_PARA_CANONICO: dict[str, str] = {}

for canonico, aliases in ALIASES.items():
    for alias in aliases:
        ALIAS_PARA_CANONICO[
            normalizar(alias)
        ] = canonico


# ============================================================
# VARIAÇÕES DE FRASES
# ============================================================
#
# Aqui ficam padrões completos que conhecemos.
#

FRASES_CONHECIDAS = {

    "tchau": (
        "tchau",
        "tchau yasmin",
        "yasmin tchau",
        "tchau yasm",
        "yasm tchau",
        "tchau yas",
        "yas tchau",
        "ate logo",
        "ate mais",
        "ate depois",
    ),

    "hora": (
        "que horas sao",
        "que horas e",
        "qual a hora",
        "qual e a hora",
        "que hora e",
        "me diga a hora",
        "me fala a hora",
        "horas agora",
    ),

    "identidade": (
        "quem e voce",
        "quem e a yasm",
        "quem e a yasmin",
        "qual e seu nome",
        "como voce se chama",
    ),

    "saudacao": (
        "oi",
        "ola",
        "ola yasmin",
        "oi yasmin",
        "e ai",
        "opa",
        "bom dia",
        "boa tarde",
        "boa noite",
    ),

    "programar_java": (
        "programar java",
        "programacao java",
        "vamos programar java",
        "ambiente java",
        "desenvolvimento java",
    ),

    "programar": (
        "programar",
        "vamos programar",
        "ir programar",
        "modo programacao",
        "ambiente de programacao",
    ),

    "bd": (
        "bd",
        "banco de dados",
        "banco de dado",
        "programar banco",
        "programar banco de dados",
    ),

    "musica": (
        "tocar musica",
        "toque uma musica",
        "coloque uma musica",
        "quero ouvir musica",
        "play musica",
        "play a music",
        "play music",
    ),

    "clima": (
        "qual o clima",
        "como esta o clima",
        "como esta o tempo",
        "qual a temperatura",
        "temperatura agora",
    ),
}


# ============================================================
# PALAVRAS IMPORTANTES
# ============================================================

PALAVRAS_IMPORTANTES = {
    "abrir",
    "abre",
    "abra",
    "iniciar",
    "inicia",
    "ligar",
    "liga",
    "fechar",
    "fecha",
    "feche",
    "encerrar",
    "encerra",
    "desligar",
    "desliga",
    "pesquisar",
    "pesquise",
    "pesquisa",
    "procurar",
    "procure",
    "buscar",
    "busque",
    "programar",
    "musica",
    "music",
    "hora",
    "horas",
    "clima",
    "tempo",
    "tchau",
    "valeu",
    "falou",
}


# ============================================================
# UTILITÁRIOS
# ============================================================

def _tokens(texto: str) -> list[str]:
    return normalizar(
        texto
    ).split()


def _similaridade(a: str, b: str) -> float:
    return SequenceMatcher(
        None,
        normalizar(a),
        normalizar(b),
    ).ratio()


def _melhor_alias(palavra: str):
    palavra_normalizada = normalizar(
        palavra
    )

    if not palavra_normalizada:
        return None, 0.0

    if palavra_normalizada in ALIAS_PARA_CANONICO:
        return (
            ALIAS_PARA_CANONICO[
                palavra_normalizada
            ],
            1.0,
        )

    melhor_nome = None
    melhor_score = 0.0

    for alias, canonico in ALIAS_PARA_CANONICO.items():

        score = SequenceMatcher(
            None,
            palavra_normalizada,
            alias,
        ).ratio()

        if score > melhor_score:
            melhor_score = score
            melhor_nome = canonico

    if melhor_score < LIMIAR_CORRECAO_BAIXA:
        return None, melhor_score

    return melhor_nome, melhor_score


def _frase_tem_palavra_importante(
    texto: str
) -> bool:

    palavras = _tokens(
        texto
    )

    return any(
        palavra in PALAVRAS_IMPORTANTES
        for palavra in palavras
    )


# ============================================================
# PASSO 1
# CORREÇÃO LEXICAL
# ============================================================

def corrigir_lexico(
    texto: str
) -> ResultadoCorrecao:

    original = str(
        texto or ""
    ).strip()

    tokens = _tokens(
        original
    )

    if not tokens:

        return ResultadoCorrecao(
            original=original,
            corrigido="",
            confianca=0.0,
            alterado=False,
            metodo="lexico",
        )

    novos_tokens = []

    alterado = False
    confiancas = []
    detalhes = []

    for token in tokens:

        if token in ALIAS_PARA_CANONICO:

            canonico = (
                ALIAS_PARA_CANONICO[
                    token
                ]
            )

            novos_tokens.append(
                canonico
            )

            confiancas.append(
                1.0
            )

            if canonico != token:

                alterado = True

                detalhes.append(
                    f"{token}->{canonico}"
                )

            continue

        canonico, confianca = (
            _melhor_alias(token)
        )

        if (
            canonico is not None
            and confianca >= LIMIAR_CORRECAO_ALTA
        ):

            novos_tokens.append(
                canonico
            )

            confiancas.append(
                confianca
            )

            if canonico != token:

                alterado = True

                detalhes.append(
                    f"{token}->{canonico}"
                )

        else:

            novos_tokens.append(
                token
            )

    corrigido = " ".join(
        novos_tokens
    )

    confianca = (
        sum(confiancas)
        / len(confiancas)
        if confiancas
        else 1.0
    )

    if not alterado:
        metodo = "lexico_inalterado"
    else:
        metodo = "lexico"

    return ResultadoCorrecao(
        original=original,
        corrigido=corrigido,
        confianca=round(
            confianca,
            4,
        ),
        alterado=alterado,
        metodo=metodo,
        detalhes=detalhes,
    )


# ============================================================
# PASSO 2
# CORREÇÃO POR SIMILARIDADE
# ============================================================

def corrigir_similaridade(
    texto: str
) -> ResultadoCorrecao:

    original = str(
        texto or ""
    ).strip()

    tokens = _tokens(
        original
    )

    if not tokens:

        return ResultadoCorrecao(
            original=original,
            corrigido="",
            confianca=0.0,
            alterado=False,
            metodo="similaridade",
        )

    novos_tokens = []

    alterado = False
    scores = []
    detalhes = []

    for token in tokens:

        if token in ALIAS_PARA_CANONICO:

            novos_tokens.append(
                ALIAS_PARA_CANONICO[
                    token
                ]
            )

            scores.append(
                1.0
            )

            if (
                ALIAS_PARA_CANONICO[
                    token
                ]
                != token
            ):
                alterado = True

            continue

        melhor, score = _melhor_alias(
            token
        )

        # ----------------------------------------------------
        # Correções fortes
        # ----------------------------------------------------

        if (
            melhor is not None
            and score >= LIMIAR_CORRECAO_MEDIA
        ):

            novos_tokens.append(
                melhor
            )

            scores.append(
                score
            )

            if melhor != token:

                alterado = True

                detalhes.append(
                    f"{token}->{melhor}"
                )

        else:

            novos_tokens.append(
                token
            )

            scores.append(
                1.0
            )

    corrigido = " ".join(
        novos_tokens
    )

    confianca = (
        sum(scores)
        / len(scores)
        if scores
        else 0.0
    )

    return ResultadoCorrecao(
        original=original,
        corrigido=corrigido,
        confianca=round(
            confianca,
            4,
        ),
        alterado=alterado,
        metodo="similaridade",
        detalhes=detalhes,
    )


# ============================================================
# COMPARADOR DE FRASES
# ============================================================

def melhor_frase_conhecida(
    texto: str,
    contexto: Iterable[str] | None = None,
):

    texto_n = normalizar(
        texto
    )

    melhor_nome = None
    melhor_frase = None
    melhor_score = 0.0

    for nome, frases in FRASES_CONHECIDAS.items():

        for frase in frases:

            score = _similaridade(
                texto_n,
                frase,
            )

            # Pequeno bônus se alguma palavra
            # importante coincidir.

            texto_tokens = set(
                _tokens(texto_n)
            )

            frase_tokens = set(
                _tokens(frase)
            )

            intersecao = (
                texto_tokens
                & frase_tokens
            )

            if intersecao:

                score += min(
                    0.12,
                    len(intersecao)
                    * 0.03,
                )

            if score > melhor_score:

                melhor_score = score
                melhor_nome = nome
                melhor_frase = frase

    # --------------------------------------------------------
    # Contexto
    # --------------------------------------------------------

    if contexto:

        for item in contexto:

            item_n = normalizar(
                item
            )

            if not item_n:
                continue

            score = _similaridade(
                texto_n,
                item_n,
            )

            score *= 0.85

            if score > melhor_score:

                melhor_score = score
                melhor_nome = (
                    "CONTEXTO"
                )
                melhor_frase = item_n

    return (
        melhor_nome,
        melhor_frase,
        min(
            1.0,
            melhor_score,
        ),
    )


# ============================================================
# PASSO 3
# CONTEXTO DA CONVERSA
# ============================================================

def corrigir_contexto(
    texto: str,
    contexto: Iterable[str] | None = None,
) -> ResultadoCorrecao:

    original = str(
        texto or ""
    ).strip()

    if not contexto:

        return ResultadoCorrecao(
            original=original,
            corrigido=original,
            confianca=0.0,
            alterado=False,
            metodo="contexto_indisponivel",
        )

    contexto_limitado = list(
        contexto
    )[
        -TAMANHO_MAXIMO_CONTEXT0:
    ]

    melhor_nome, melhor_frase, score = (
        melhor_frase_conhecida(
            original,
            contexto_limitado,
        )
    )

    if (
        melhor_frase is None
        or score < LIMIAR_CORRECAO_MEDIA
    ):

        return ResultadoCorrecao(
            original=original,
            corrigido=original,
            confianca=score,
            alterado=False,
            metodo="contexto_sem_correcao",
        )

    # --------------------------------------------------------
    # Só substitui quando a similaridade é alta.
    # --------------------------------------------------------

    if (
        melhor_nome == "CONTEXTO"
        and score >= LIMIAR_CORRECAO_ALTA
    ):

        return ResultadoCorrecao(
            original=original,
            corrigido=melhor_frase,
            confianca=score,
            alterado=(
                normalizar(original)
                != normalizar(melhor_frase)
            ),
            metodo="contexto",
            detalhes=[
                "frase aproximada encontrada no contexto"
            ],
        )

    if (
        melhor_nome != "CONTEXTO"
        and score >= LIMIAR_CORRECAO_MEDIA
    ):

        return ResultadoCorrecao(
            original=original,
            corrigido=original,
            confianca=score,
            alterado=False,
            metodo="contexto_intencao",
            detalhes=[
                f"possivel intencao: {melhor_nome}",
                f"frase_proxima: {melhor_frase}",
            ],
        )

    return ResultadoCorrecao(
        original=original,
        corrigido=original,
        confianca=score,
        alterado=False,
        metodo="contexto_sem_correcao",
    )


# ============================================================
# PASSO 4
# DESAMBIGUAÇÃO POR INTENÇÃO
# ============================================================

def corrigir_por_intencao(
    texto: str,
    intencoes: dict[str, Iterable[str]] | None = None,
) -> ResultadoCorrecao:

    original = str(
        texto or ""
    ).strip()

    if not intencoes:

        # Usa as frases conhecidas do próprio corretor.
        intencoes = FRASES_CONHECIDAS

    texto_n = normalizar(
        original
    )

    melhor_intencao = None
    melhor_frase = None
    melhor_score = 0.0

    for nome, frases in intencoes.items():

        for frase in frases:

            frase_n = normalizar(
                frase
            )

            score = SequenceMatcher(
                None,
                texto_n,
                frase_n,
            ).ratio()

            texto_tokens = set(
                _tokens(texto_n)
            )

            frase_tokens = set(
                _tokens(frase_n)
            )

            iguais = (
                texto_tokens
                & frase_tokens
            )

            if iguais:

                score += min(
                    0.15,
                    len(iguais)
                    * 0.04,
                )

            if score > melhor_score:

                melhor_score = score

                melhor_intencao = nome

                melhor_frase = frase

    if (
        melhor_intencao is None
        or melhor_score < LIMIAR_CORRECAO_BAIXA
    ):

        return ResultadoCorrecao(
            original=original,
            corrigido=original,
            confianca=melhor_score,
            alterado=False,
            metodo="intencao_sem_correcao",
        )

    # --------------------------------------------------------
    # Correção de alta confiança.
    # --------------------------------------------------------

    if melhor_score >= LIMIAR_CORRECAO_MEDIA:

        return ResultadoCorrecao(
            original=original,
            corrigido=normalizar(
                melhor_frase
            ),
            confianca=min(
                1.0,
                melhor_score,
            ),
            alterado=(
                normalizar(original)
                != normalizar(
                    melhor_frase
                )
            ),
            metodo="intencao",
            detalhes=[
                f"intencao={melhor_intencao}",
                f"frase={melhor_frase}",
            ],
        )

    return ResultadoCorrecao(
        original=original,
        corrigido=original,
        confianca=melhor_score,
        alterado=False,
        metodo="intencao_baixa_confianca",
        detalhes=[
            f"possivel_intencao={melhor_intencao}",
            f"frase={melhor_frase}",
        ],
    )


# ============================================================
# PROTEÇÃO CONTRA CORREÇÕES ABSURDAS
# ============================================================

def _correcao_segura(
    original: str,
    candidato: str,
) -> bool:

    original_tokens = _tokens(
        original
    )

    candidato_tokens = _tokens(
        candidato
    )

    if not candidato_tokens:
        return False

    # Não deixar o corretor criar frases enormes.
    if (
        len(candidato_tokens)
        > len(original_tokens)
        + MAXIMO_PALAVRAS_DIFERENTES
    ):
        return False

    # Alteração global muito grande exige
    # confiança mais alta.
    diferenca = abs(
        len(candidato_tokens)
        - len(original_tokens)
    )

    if diferenca > 2:
        return False

    return True


# ============================================================
# PIPELINE COMPLETO
# ============================================================

def corrigir(
    texto: str,
    contexto: Iterable[str] | None = None,
    intencoes: dict[str, Iterable[str]] | None = None,
) -> ResultadoCorrecao:

    original = str(
        texto or ""
    ).strip()

    if not original:

        return ResultadoCorrecao(
            original="",
            corrigido="",
            confianca=0.0,
            alterado=False,
            metodo="vazio",
        )

    # ========================================================
    # PASSO 1
    # LEXICAL
    # ========================================================

    resultado_lexico = corrigir_lexico(
        original
    )

    texto_atual = (
        resultado_lexico.corrigido
    )

    melhor_resultado = (
        resultado_lexico
    )

    # ========================================================
    # PASSO 2
    # SIMILARIDADE
    # ========================================================

    resultado_similaridade = (
        corrigir_similaridade(
            texto_atual
        )
    )

    if (
        resultado_similaridade.confianca
        > melhor_resultado.confianca
    ):

        melhor_resultado = (
            resultado_similaridade
        )

    if (
        resultado_similaridade.alterado
        and _correcao_segura(
            original,
            resultado_similaridade.corrigido,
        )
    ):

        texto_atual = (
            resultado_similaridade.corrigido
        )

    # ========================================================
    # PASSO 3
    # CONTEXTO
    # ========================================================

    resultado_contexto = (
        corrigir_contexto(
            texto_atual,
            contexto,
        )
    )

    if (
        resultado_contexto.alterado
        and resultado_contexto.confianca
        >= LIMIAR_CORRECAO_ALTA
        and _correcao_segura(
            original,
            resultado_contexto.corrigido,
        )
    ):

        texto_atual = (
            resultado_contexto.corrigido
        )

    if (
        resultado_contexto.confianca
        > melhor_resultado.confianca
    ):

        melhor_resultado = (
            resultado_contexto
        )

    # ========================================================
    # PASSO 4
    # INTENÇÃO
    # ========================================================

    resultado_intencao = (
        corrigir_por_intencao(
            texto_atual,
            intencoes,
        )
    )

    if (
        resultado_intencao.alterado
        and resultado_intencao.confianca
        >= LIMIAR_CORRECAO_ALTA
        and _correcao_segura(
            original,
            resultado_intencao.corrigido,
        )
    ):

        texto_atual = (
            resultado_intencao.corrigido
        )

    if (
        resultado_intencao.confianca
        > melhor_resultado.confianca
    ):

        melhor_resultado = (
            resultado_intencao
        )

    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    alterado = (
        normalizar(original)
        != normalizar(texto_atual)
    )

    if alterado:

        confianca = max(
            resultado_lexico.confianca,
            resultado_similaridade.confianca,
            resultado_contexto.confianca,
            resultado_intencao.confianca,
        )

        detalhes = []

        detalhes.extend(
            resultado_lexico.detalhes
        )

        detalhes.extend(
            resultado_similaridade.detalhes
        )

        detalhes.extend(
            resultado_contexto.detalhes
        )

        detalhes.extend(
            resultado_intencao.detalhes
        )

        return ResultadoCorrecao(
            original=original,
            corrigido=texto_atual,
            confianca=round(
                min(
                    1.0,
                    confianca,
                ),
                4,
            ),
            alterado=True,
            metodo="pipeline",
            detalhes=detalhes,
        )

    return ResultadoCorrecao(
        original=original,
        corrigido=original,
        confianca=round(
            melhor_resultado.confianca,
            4,
        ),
        alterado=False,
        metodo=melhor_resultado.metodo,
        detalhes=melhor_resultado.detalhes,
    )


# ============================================================
# FUNÇÃO SIMPLES
# ============================================================

def corrigir_texto(
    texto: str,
    contexto: Iterable[str] | None = None,
    intencoes: dict[str, Iterable[str]] | None = None,
) -> str:

    return corrigir(
        texto,
        contexto=contexto,
        intencoes=intencoes,
    ).corrigido


# ============================================================
# TESTE
# ============================================================

if __name__ == "__main__":

    testes = (
        "tchao yasmin",
        "yasmin tchau",
        "tchau yasmin",
        "que oras sao",
        "qual a hora",
        "abre o vs code",
        "abre o v s code",
        "programar java",
        "my sql workbench",
        "servidor xamp",
        "pesquiza pra mim",
        "quem e voce",
        "piton",
        "paiton",
        "obrigadu",
        "falou yasmin",
        "xau yas",
    )

    contexto = (
        "Yasmin tá aí",
        "consegue olhar para mim quem ganhou a copa",
        "qual é o horário agora",
        "vamos programar java",
        "abre o VS Code",
    )

    print(
        "=" * 72
    )

    print(
        "TESTE DO CORRETOR DA YASM"
    )

    print(
        "=" * 72
    )

    for texto in testes:

        resultado = corrigir(
            texto,
            contexto=contexto,
        )

        print()
        print(
            f"Original : {resultado.original}"
        )

        print(
            f"Corrigido: {resultado.corrigido}"
        )

        print(
            f"Confiança: {resultado.confianca:.3f}"
        )

        print(
            f"Alterado : {resultado.alterado}"
        )

        print(
            f"Método   : {resultado.metodo}"
        )

        if resultado.detalhes:

            print(
                f"Detalhes : {resultado.detalhes}"
            )