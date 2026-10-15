import json
import os
import tempfile
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from config_yasm import ARQUIVO_MEMORIA


_memoria_lock = threading.RLock()


# ============================================================
# CARREGAR MEMÓRIA
# ============================================================

def carregar_memoria():
    """
    Carrega a memória persistente da Yasm.

    Caso o arquivo não exista ou esteja corrompido,
    retorna uma memória vazia.
    """

    if not ARQUIVO_MEMORIA.exists():
        return {}

    try:

        with ARQUIVO_MEMORIA.open(
            "r",
            encoding="utf-8"
        ) as arquivo:

            dados = json.load(
                arquivo
            )

            if isinstance(
                dados,
                dict
            ):
                return dados

            return {}

    except (
        json.JSONDecodeError,
        OSError,
        TypeError,
        ValueError,
    ):

        return {}


# ============================================================
# SALVAR MEMÓRIA
# ============================================================

def salvar_json_atomico(caminho, dados):
    """Substitui o JSON somente depois de serializar e gravar tudo."""
    temporario = None
    with _memoria_lock:
        try:
            conteudo = json.dumps(dados, ensure_ascii=False, indent=4, allow_nan=False)
            caminho = Path(caminho)
            caminho.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=caminho.parent,
                prefix=f".{caminho.name}.", suffix=".tmp", delete=False,
            ) as arquivo:
                temporario = Path(arquivo.name)
                arquivo.write(conteudo)
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, caminho)
            return True
        except (OSError, TypeError, ValueError, RuntimeError) as erro:
            print(
                "[Memória] Erro ao salvar memória: "
                f"{type(erro).__name__}: {erro!r}"
            )
            return False
        finally:
            if temporario is not None:
                try:
                    temporario.unlink(missing_ok=True)
                except OSError:
                    pass


def salvar_memoria(memoria):
    """Salva a memória sem deixar um JSON parcial em caso de falha."""
    return salvar_json_atomico(ARQUIVO_MEMORIA, memoria)


# ============================================================
# MEMÓRIA BASE
# ============================================================

def garantir_memoria_base(memoria):
    """
    Garante que todas as estruturas necessárias existam.

    Nunca remove informações existentes.
    """

    if not isinstance(memoria, dict):
        memoria = {}

    # ========================================================
    # USUÁRIO
    # ========================================================

    memoria.setdefault(
        "usuario",
        {}
    )

    if not isinstance(
        memoria["usuario"],
        dict
    ):
        memoria["usuario"] = {}


    # ========================================================
    # ASSISTENTE
    # ========================================================

    memoria.setdefault(
        "assistente",
        {}
    )

    if not isinstance(
        memoria["assistente"],
        dict
    ):
        memoria["assistente"] = {}


    # ========================================================
    # VOZ
    # ========================================================

    memoria.setdefault(
        "voz",
        {}
    )

    if not isinstance(
        memoria["voz"],
        dict
    ):
        memoria["voz"] = {}


    # ========================================================
    # CONFIGURAÇÃO
    # ========================================================

    memoria.setdefault(
        "configuracao",
        {}
    )

    if not isinstance(
        memoria["configuracao"],
        dict
    ):
        memoria["configuracao"] = {}

    memoria["configuracao"].setdefault(
        "concluida",
        False
    )

    if not isinstance(memoria["configuracao"]["concluida"], bool):
        memoria["configuracao"]["concluida"] = False


    # ========================================================
    # PREFERÊNCIAS
    # ========================================================

    memoria.setdefault(
        "preferencias",
        {}
    )

    if not isinstance(
        memoria["preferencias"],
        dict
    ):
        memoria["preferencias"] = {}


    # ========================================================
    # NOTAS
    # ========================================================

    memoria.setdefault(
        "notas",
        []
    )

    if not isinstance(
        memoria["notas"],
        list
    ):
        memoria["notas"] = []


    # ========================================================
    # TAREFAS
    # ========================================================

    memoria.setdefault(
        "tarefas",
        []
    )

    if not isinstance(
        memoria["tarefas"],
        list
    ):
        memoria["tarefas"] = []


    # ========================================================
    # HISTÓRICO
    # ========================================================

    memoria.setdefault(
        "historico",
        []
    )

    if not isinstance(
        memoria["historico"],
        list
    ):
        memoria["historico"] = []


    # ========================================================
    # PESQUISAS
    # ========================================================

    memoria.setdefault(
        "pesquisas",
        []
    )

    if not isinstance(
        memoria["pesquisas"],
        list
    ):
        memoria["pesquisas"] = []


    # ========================================================
    # ESTUDO
    # ========================================================

    memoria.setdefault(
        "estudo",
        {}
    )

    if not isinstance(
        memoria["estudo"],
        dict
    ):
        memoria["estudo"] = {}

    estudo = memoria[
        "estudo"
    ]

    estudo.setdefault(
        "nivel",
        "iniciante"
    )

    estudo.setdefault(
        "topicos_vistos",
        []
    )

    estudo.setdefault(
        "exercicios",
        []
    )

    estudo.setdefault(
        "quiz_atual",
        None
    )

    estudo.setdefault(
        "pontuacao_quiz",
        0
    )

    estudo.setdefault(
        "sessoes",
        []
    )

    if not isinstance(
        estudo["topicos_vistos"],
        list
    ):
        estudo["topicos_vistos"] = []

    if not isinstance(
        estudo["exercicios"],
        list
    ):
        estudo["exercicios"] = []

    if not isinstance(
        estudo["sessoes"],
        list
    ):
        estudo["sessoes"] = []

    if type(estudo["pontuacao_quiz"]) is not int or estudo["pontuacao_quiz"] < 0:
        estudo["pontuacao_quiz"] = 0
    if estudo["quiz_atual"] is not None and (
        type(estudo["quiz_atual"]) is not int or estudo["quiz_atual"] < 0
    ):
        estudo["quiz_atual"] = None


    return memoria


# ============================================================
# CARREGAMENTO INICIAL
# ============================================================

memoria = garantir_memoria_base(
    carregar_memoria()
)


# ============================================================
# HISTÓRICO
# ============================================================

def registrar_historico(
    tipo,
    texto,
):
    """
    Registra uma mensagem no histórico persistente.

    Mantém somente as últimas 30 entradas.
    """

    memoria.setdefault(
        "historico",
        []
    )

    memoria["historico"].append(
        {
            "tipo": str(tipo),
            "texto": str(texto),
            "criado_em": datetime.now().isoformat(
                timespec="seconds"
            ),
        }
    )

    memoria["historico"] = (
        memoria["historico"][-30:]
    )

    salvar_memoria(
        memoria
    )


# ============================================================
# CONFIGURAÇÃO
# ============================================================

def configuracao_pronta():
    """
    Retorna True quando o questionário inicial já foi concluído.
    """

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


def marcar_configuracao_concluida():
    """
    Marca a configuração inicial como concluída.
    """

    memoria.setdefault(
        "configuracao",
        {}
    )[
        "concluida"
    ] = True

    memoria[
        "configuracao"
    ][
        "concluida_em"
    ] = datetime.now().isoformat(
        timespec="seconds"
    )

    salvar_memoria(
        memoria
    )


# ============================================================
# CONFIGURAÇÃO DO USUÁRIO
# ============================================================

def obter_nome_usuario(
    padrao="amigo"
):
    return (
        memoria
        .get(
            "usuario",
            {}
        )
        .get(
            "nome",
            padrao
        )
    )


def definir_nome_usuario(
    nome
):
    memoria.setdefault(
        "usuario",
        {}
    )[
        "nome"
    ] = str(
        nome
    ).strip()

    salvar_memoria(
        memoria
    )


# ============================================================
# CONFIGURAÇÃO DA ASSISTENTE
# ============================================================

def obter_nome_assistente(
    padrao="Yasm"
):
    return (
        memoria
        .get(
            "assistente",
            {}
        )
        .get(
            "nome",
            padrao
        )
    )


def definir_nome_assistente(
    nome
):
    memoria.setdefault(
        "assistente",
        {}
    )[
        "nome"
    ] = str(
        nome
    ).strip()

    salvar_memoria(
        memoria
    )


# ============================================================
# CONFIGURAÇÃO DE VOZ
# ============================================================

def obter_voz(
    padrao="pt-BR-FranciscaNeural"
):
    return (
        memoria
        .get(
            "voz",
            {}
        )
        .get(
            "id",
            padrao
        )
    )


def definir_voz(
    voz_id
):
    memoria.setdefault(
        "voz",
        {}
    )[
        "id"
    ] = str(
        voz_id
    ).strip()

    salvar_memoria(
        memoria
    )


# ============================================================
# PREFERÊNCIAS
# ============================================================

def obter_preferencia(
    chave,
    padrao=None,
):
    return (
        memoria
        .get(
            "preferencias",
            {}
        )
        .get(
            chave,
            padrao
        )
    )


def definir_preferencia(
    chave,
    valor,
):
    memoria.setdefault(
        "preferencias",
        {}
    )[
        chave
    ] = valor

    salvar_memoria(
        memoria
    )


# ============================================================
# RESET DA CONFIGURAÇÃO
# ============================================================

def resetar_configuracao():
    """
    Remove somente os dados relacionados à configuração inicial.

    Não apaga:
    - notas;
    - tarefas;
    - pesquisas;
    - histórico;
    - estudos.
    """

    memoria[
        "usuario"
    ] = {}

    memoria[
        "assistente"
    ] = {}

    memoria[
        "voz"
    ] = {}

    memoria[
        "preferencias"
    ] = {}

    memoria[
        "configuracao"
    ] = {
        "concluida": False
    }

    salvar_memoria(
        memoria
    )


# ============================================================
# SALVAR CONFIGURAÇÃO COMPLETA
# ============================================================

def salvar_configuracao(
    *,
    nome_usuario=None,
    nome_assistente=None,
    voz_id=None,
    preferencias=None,
):
    """
    Salva várias configurações de uma vez.

    Somente os valores fornecidos são alterados.
    """

    if nome_usuario is not None:

        memoria.setdefault(
            "usuario",
            {}
        )[
            "nome"
        ] = str(
            nome_usuario
        ).strip()


    if nome_assistente is not None:

        memoria.setdefault(
            "assistente",
            {}
        )[
            "nome"
        ] = str(
            nome_assistente
        ).strip()


    if voz_id is not None:

        memoria.setdefault(
            "voz",
            {}
        )[
            "id"
        ] = str(
            voz_id
        ).strip()


    if preferencias is not None:

        if isinstance(
            preferencias,
            dict
        ):

            memoria.setdefault(
                "preferencias",
                {}
            ).update(
                preferencias
            )


    salvar_memoria(
        memoria
    )


# ============================================================
# EXPORTAÇÃO DE CONFIGURAÇÃO
# ============================================================

def obter_configuracao():
    """
    Retorna uma cópia da configuração atual.
    """

    return deepcopy({
        "usuario": dict(
            memoria.get(
                "usuario",
                {}
            )
        ),
        "assistente": dict(
            memoria.get(
                "assistente",
                {}
            )
        ),
        "voz": dict(
            memoria.get(
                "voz",
                {}
            )
        ),
        "preferencias": dict(
            memoria.get(
                "preferencias",
                {}
            )
        ),
        "configuracao": dict(
            memoria.get(
                "configuracao",
                {}
            )
        ),
    })
