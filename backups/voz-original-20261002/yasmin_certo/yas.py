import sys
import time
import socket

from config_yasm import (
    TEMPO_ESPERA_CONVERSA,
    TEMPO_MODO_CONVERSA,
    DEBUG,
    OFFLINE_PRIMEIRO,
)

from memoria_yasm import (
    memoria,
    salvar_memoria,
    registrar_historico,
)

from util_yasm import normalizar

import voz_yasm as voz
import audio_yasm as audio
import comandos_yasm as comandos
import apps_yas as apps
import falas
import intent

from cerebro.cerebro import cerebro
from interface import config_inicial


# ============================================================
# CONFIGURAÇÃO DE COMUNICAÇÃO COM O LAUNCHER
# ============================================================

HOST_LAUNCHER = "127.0.0.1"
PORTA_STATUS = 45454


def avisar_yasm_online():
    """
    Avisa o launcher que a Yasm terminou a calibração
    e está pronta para funcionar.
    """

    try:
        cliente = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM,
        )

        cliente.sendto(
            b"ONLINE",
            (
                HOST_LAUNCHER,
                PORTA_STATUS,
            ),
        )

        cliente.close()

    except Exception as erro:

        if DEBUG:
            print(
                "[Status] Nao consegui avisar o launcher: "
                f"{type(erro).__name__}: {erro!r}"
            )


# ============================================================
# CONFIGURAÇÃO DE NOME
# ============================================================

NOMES_INVALIDOS = {
    "oi",
    "ola",
    "e ai",
    "eai",
    "opa",
    "hey",
    "hello",
    "mano",
    "amigo",
    "amiga",
    "obrigado",
    "obrigada",
    "sim",
    "nao",
}


def nome_salvo():
    return (
        memoria
        .get(
            "usuario",
            {},
        )
        .get(
            "nome",
            "amigo",
        )
    )


def descobrir_nome():
    """
    Descobre o nome do usuario caso a configuracao inicial
    ainda nao tenha definido um nome valido.
    """

    voz.falar(
        falas.escolher(
            "pergunta_nome"
        )
    )

    for _ in range(3):

        resposta = audio.escutar(
            timeout=8.0,
            silencioso=True,
        )

        resposta = normalizar(
            resposta
        )

        if not resposta:
            continue

        nome = resposta

        for gatilho in (
            "meu nome e",
            "me chamo",
            "eu sou",
            "pode me chamar de",
        ):

            if gatilho in nome:

                nome = (
                    nome
                    .split(
                        gatilho,
                        1,
                    )[1]
                    .strip()
                )

                break

        nome = nome.strip(
            " .,?!"
        )

        partes = nome.split()

        if not partes:
            continue

        if len(partes) > 4:
            continue

        if nome in NOMES_INVALIDOS:
            continue

        partes_validas = [
            parte
            for parte in partes
            if parte not in NOMES_INVALIDOS
        ]

        if not partes_validas:
            continue

        nome = " ".join(
            partes_validas
        )

        if len(nome) < 2:
            continue

        return nome.title()

    return "amigo"


def configurar_usuario():
    """
    Recupera o nome salvo.

    A configuracao inicial normalmente ja tera salvo o nome.
    O fallback abaixo existe para manter compatibilidade com
    memoria antiga ou configuracao incompleta.
    """

    nome = nome_salvo()

    if nome != "amigo":
        try:
            cerebro.lembrar_usuario(
                "nome",
                nome,
            )
        except Exception:
            pass

        return nome

    nome = descobrir_nome()

    memoria.setdefault(
        "usuario",
        {},
    )["nome"] = nome

    salvar_memoria(
        memoria
    )

    try:
        cerebro.lembrar_usuario(
            "nome",
            nome,
        )
    except Exception:
        pass

    try:
        voz.falar(
            falas.escolher(
                "nome_alterado",
                nome=nome,
            )
        )
    except Exception:
        pass

    return nome


# ============================================================
# CONTEXTO PARA O CORRETOR
# ============================================================

def contexto_para_corretor():
    """
    Recupera as ultimas falas do historico para permitir que
    o corretor considere o contexto da conversa.
    """

    historico = memoria.get(
        "historico",
        [],
    )

    contexto = []

    for item in historico[-8:]:

        if not isinstance(
            item,
            dict,
        ):
            continue

        texto = item.get(
            "texto",
            "",
        )

        if texto:
            contexto.append(
                str(texto)
            )

    return contexto


# ============================================================
# PESQUISA FALLBACK
# ============================================================

def _pesquisar_fallback(texto):
    """
    Tenta utilizar as pesquisas ja existentes no projeto.
    """

    consulta = normalizar(
        texto
    )

    if not consulta:
        return None

    # --------------------------------------------------------
    # PESQUISA WEB DIRETA
    # --------------------------------------------------------

    try:

        pesquisar_google = getattr(
            comandos,
            "pesquisar_google",
            None,
        )

        if callable(
            pesquisar_google
        ):

            resposta = pesquisar_google(
                consulta
            )

            if resposta:
                return resposta

    except Exception as erro:

        if DEBUG:
            print(
                "[Intent] Falha na pesquisa web: "
                f"{type(erro).__name__}: {erro!r}"
            )

    # --------------------------------------------------------
    # PESQUISA PELO DISPATCHER ANTIGO
    # --------------------------------------------------------

    try:

        pesquisar_comando = getattr(
            comandos,
            "pesquisar_comando",
            None,
        )

        if callable(
            pesquisar_comando
        ):

            resposta = pesquisar_comando(
                consulta
            )

            if resposta:
                return resposta

    except Exception as erro:

        if DEBUG:
            print(
                "[Intent] Falha no dispatcher de pesquisa: "
                f"{type(erro).__name__}: {erro!r}"
            )

    return None


# ============================================================
# DISPATCHER PRINCIPAL
# ============================================================

def processar_comando(texto):
    """
    Dispatcher principal da Yasm.

    Ordem:

        1. recebe a transcricao;
        2. corrige a frase atraves do intent/corretor;
        3. verifica encerramento;
        4. executa aplicativos;
        5. executa atalhos;
        6. trata pesquisa;
        7. executa intencoes locais;
        8. faz fallback para pesquisa.
    """

    texto_original = str(
        texto or ""
    ).strip()

    if not texto_original:

        return falas.escolher(
            "chamada",
            nome=nome_salvo(),
        )

    # ========================================================
    # INTENT + CORRETOR
    # ========================================================

    try:

        interpretacao = intent.interpretar(
            texto_original,
            contexto=contexto_para_corretor(),
            fallback_pesquisa=False,
        )

    except TypeError:

        # Compatibilidade caso a versao atual do intent.py
        # ainda nao aceite o parametro contexto.

        try:

            interpretacao = intent.interpretar(
                texto_original,
                fallback_pesquisa=False,
            )

        except Exception as erro:

            if DEBUG:
                print(
                    "[Intent] Erro na interpretacao: "
                    f"{type(erro).__name__}: {erro!r}"
                )

            interpretacao = None

    except Exception as erro:

        if DEBUG:
            print(
                "[Intent] Erro na interpretacao: "
                f"{type(erro).__name__}: {erro!r}"
            )

        interpretacao = None

    # ========================================================
    # FALLBACK SE O INTENT FALHAR
    # ========================================================

    if interpretacao is None:
        return falas.escolher(
            "nao_entendi"
        )

    # ========================================================
    # TEXTO CORRIGIDO
    # ========================================================

    texto_limpo = (
        interpretacao.texto_corrigido
        or interpretacao.texto_normalizado
        or intent.remover_chamada(
            texto_original
        )
    )

    texto_limpo = normalizar(
        texto_limpo
    )

    # ========================================================
    # ENCERRAMENTO ABSOLUTO
    # ========================================================

    if interpretacao.nome == "ENCERRAR":

        return "encerrar"

    # ========================================================
    # CHAMADA CURTA
    # ========================================================

    if interpretacao.nome == "CHAMADA_CURTA":

        return falas.escolher(
            "chamada",
            nome=nome_salvo(),
        )

    if interpretacao.nome == "DESCONHECIDA" and memoria.get("estudo", {}).get("quiz_atual") is not None:
        resposta = comandos.responder_quiz_python(texto_original)
        if resposta:
            return resposta

    # ========================================================
    # MUSICA
    # ========================================================
    #
    # Deve vir antes da pesquisa: nomes de musicas soltos
    # parecem pesquisas, mas podem ser a resposta ao pedido
    # anterior "toque uma musica".

    try:

        if (
            getattr(
                comandos,
                "musica_pendente",
                lambda: False,
            )()
            or interpretacao.nome == "MUSICA"
        ):

            resposta = comandos.responder(
                texto_limpo
                or texto_original
            )

            if resposta:
                return resposta

    except Exception as erro:

        if DEBUG:
            print(
                "[Musica] Erro ao processar musica: "
                f"{type(erro).__name__}: {erro!r}"
            )

    # ========================================================
    # APLICATIVOS
    # ========================================================

    if interpretacao.nome in {
        "ABRIR_APLICATIVO",
        "FECHAR_APLICATIVO",
    }:

        aplicativo = (
            interpretacao
            .parametros
            .get(
                "aplicativo"
            )
        )

        if aplicativo:

            try:

                if (
                    interpretacao.nome
                    == "ABRIR_APLICATIVO"
                ):

                    return apps.abrir_aplicativo(
                        aplicativo
                    )

                return apps.fechar_aplicativo(
                    aplicativo
                )

            except Exception as erro:

                if DEBUG:
                    print(
                        "[Apps] Erro no aplicativo: "
                        f"{type(erro).__name__}: {erro!r}"
                    )

        # ----------------------------------------------------
        # Compatibilidade com o sistema antigo
        # ----------------------------------------------------

        try:

            resposta = (
                apps
                .comando_abrir_aplicativo(
                    texto_limpo
                )
            )

            if resposta:
                return resposta

        except Exception as erro:

            if DEBUG:
                print(
                    "[Apps] Erro ao abrir aplicativo: "
                    f"{type(erro).__name__}: {erro!r}"
                )

        try:

            resposta = (
                apps
                .comando_fechar_aplicativo(
                    texto_limpo
                )
            )

            if resposta:
                return resposta

        except Exception as erro:

            if DEBUG:
                print(
                    "[Apps] Erro ao fechar aplicativo: "
                    f"{type(erro).__name__}: {erro!r}"
                )

    # ========================================================
    # ATALHOS
    # ========================================================

    if interpretacao.nome in {
        "ATALHO_JAVA",
        "ATALHO_PROGRAMAR",
        "ATALHO_BANCO",
    }:

        comando_atalho = getattr(
            apps,
            "comando_atalho",
            None,
        )

        if callable(
            comando_atalho
        ):

            atalhos = {
                "ATALHO_JAVA": "programar java",
                "ATALHO_PROGRAMAR": "programar",
                "ATALHO_BANCO": "bd",
            }

            atalho = atalhos[
                interpretacao.nome
            ]

            try:

                resposta = comando_atalho(
                    atalho
                )

                if resposta:
                    return resposta

            except Exception as erro:

                if DEBUG:
                    print(
                        "[Apps] Erro no atalho: "
                        f"{type(erro).__name__}: {erro!r}"
                    )

    # ========================================================
    # PESQUISA EXPLÍCITA
    # ========================================================

    if interpretacao.nome == "PESQUISA":

        resposta = _pesquisar_fallback(
            texto_limpo
        )

        if resposta:
            return resposta

        return falas.escolher(
            "pesquisa_falhou"
        )

    # ========================================================
    # INTENÇÃO LOCAL
    # ========================================================

    if interpretacao.nome != "DESCONHECIDA":

        try:

            resposta = comandos.responder(
                texto_original if interpretacao.nome == "CALCULO" else texto_limpo
            )

            if resposta:

                return resposta

        except Exception as erro:

            if DEBUG:
                print(
                    "[Comandos] Erro ao processar "
                    f"intencao: {type(erro).__name__}: {erro!r}"
                )

    # ========================================================
    # FALLBACK LOCAL
    # ========================================================

    return falas.escolher(
        "nao_entendi"
    )


# ============================================================
# MODO DE CONVERSA
# ============================================================

def conversar(texto_inicial=None):
    """
    Entra no modo de conversa depois que o usuario chama
    a Yasm.
    """

    nome = configurar_usuario()

    if not texto_inicial or not intent.remover_chamada(texto_inicial):
        texto_inicial = None
        voz.falar(falas.escolher("ouvindo_nome", nome=nome))

    inicio_modo = time.monotonic()

    while (
        time.monotonic() - inicio_modo
        < TEMPO_MODO_CONVERSA
    ):

        if texto_inicial:
            texto, texto_inicial = texto_inicial, None
        else:
            texto = audio.escutar(timeout=TEMPO_ESPERA_CONVERSA)

        if not texto:
            return

        # ----------------------------------------------------
        # HISTORICO
        # ----------------------------------------------------

        registrar_historico(
            "usuario",
            texto,
        )

        inicio_modo = time.monotonic()

        # ----------------------------------------------------
        # PROCESSAMENTO
        # ----------------------------------------------------

        resposta = processar_comando(
            texto
        )

        # ----------------------------------------------------
        # ENCERRAMENTO
        # ----------------------------------------------------

        if resposta == "encerrar":

            voz.falar(
                falas.escolher(
                    "despedida",
                    nome=nome,
                )
            )

            sys.exit(0)

        # ----------------------------------------------------
        # RESPOSTA
        # ----------------------------------------------------

        if resposta:

            registrar_historico(
                "yasm",
                resposta,
            )

            voz.falar(
                resposta
            )


# ============================================================
# CONFIGURAÇÃO INICIAL
# ============================================================

def executar_configuracao_inicial():
    """
    Executa o questionario somente quando a Yasm ainda
    nao possui uma configuracao concluida.
    """

    try:

        if not config_inicial.precisa_configurar():
            return

    except Exception as erro:

        if DEBUG:
            print(
                "[Configuracao] Erro ao verificar configuracao: "
                f"{type(erro).__name__}: {erro!r}"
            )

        return

    try:

        config_inicial.iniciar()

    except Exception as erro:

        print(
            "[Erro] Falha na configuracao inicial: "
            f"{type(erro).__name__}: {erro!r}"
        )

        if DEBUG:

            import traceback

            traceback.print_exc()

        return


# ============================================================
# MAIN
# ============================================================

def main(texto_inicial=None):

    print(
        "=" * 55
    )

    print(
        "                    YASM"
    )

    print(
        "=" * 55
    )

    print(
        f"Reconhecimento de voz: {audio.motor_reconhecimento()}"
    )

    print(
        "Entrada de audio: sounddevice"
    )

    print(
        "Modo: offline primeiro" if OFFLINE_PRIMEIRO else "Modo: hibrido"
    )

    print("")

    # ========================================================
    # CALIBRAÇÃO
    # ========================================================

    try:

        audio.calibrar_sounddevice()
        audio.preparar_reconhecimento()

    except Exception as erro:

        print(
            "[Erro] Nao consegui iniciar o microfone: "
            f"{type(erro).__name__}: {erro!r}"
        )

        return 1

    # ========================================================
    # CONFIGURAÇÃO INICIAL
    # ========================================================

    executar_configuracao_inicial()

    # ========================================================
    # SINCRONIZAR USUÁRIO COM O CÉREBRO
    # ========================================================

    try:

        nome = nome_salvo()

        if nome != "amigo":

            cerebro.lembrar_usuario(
                "nome",
                nome,
            )

    except Exception as erro:

        if DEBUG:

            print(
                "[Cerebro] Falha ao sincronizar usuario: "
                f"{type(erro).__name__}: {erro!r}"
            )

    # ========================================================
    # AVISAR O LAUNCHER
    # ========================================================

    avisar_yasm_online()

    # ========================================================
    # SISTEMA PRONTO
    # ========================================================

    try:

        voz.falar(
            falas.escolher(
                "sistema_online"
            )
        )

    except Exception as erro:

        if DEBUG:

            print(
                "[Voz] Falha ao falar inicializacao: "
                f"{type(erro).__name__}: {erro!r}"
            )

    # ========================================================
    # LOOP PRINCIPAL
    # ========================================================

    if texto_inicial:
        conversar(texto_inicial)

    while True:

        try:

            texto = audio.escutar(
                timeout=None
            )

            if (
                texto
                and intent.chamou_yasm(
                    texto
                )
            ):

                conversar(texto)

        except KeyboardInterrupt:

            nome = nome_salvo()

            try:

                voz.falar(
                    falas.escolher(
                        "despedida",
                        nome=nome,
                    )
                )

            except Exception:
                pass

            break

        except SystemExit:

            raise

        except Exception as erro:

            print(
                "[Erro interno] "
                f"{type(erro).__name__}: {erro!r}"
            )

            if DEBUG:

                import traceback

                traceback.print_exc()

            time.sleep(
                0.2
            )


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Assistente de voz Yasm")
    parser.add_argument("--comando", help="Comando recebido pelo launcher")
    raise SystemExit(main(parser.parse_args().comando))
