import sys
import time
import socket
import threading

from pipeline_voz import Estado, MaquinaEstados, EntregaUnica, metricas
from ativacao_yasm import remover_prefixo

estados = MaquinaEstados()
entregas = EntregaUnica()

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
import logging

from agente.raciocinio import RegrasDeterministicas
from agente.integracao_aplicacoes.raciocinio import RaciocinioAplicacoes
from agente.pedidos_dev import RaciocinioDev
from pathlib import Path

_raciocinio_agente = RaciocinioDev(RaciocinioAplicacoes(
    RegrasDeterministicas(), Path(__file__).resolve().parent.parent / "applications"))
_agente = None
_conversacao = None
_motor_decisao = None
_trava_comandos = threading.RLock()
if DEBUG:
    _log_agente = logging.getLogger("yasm.agente")
    _log_agente.setLevel(logging.DEBUG)
    if not _log_agente.handlers:
        _log_agente.addHandler(logging.StreamHandler())


def inicializar_agente():
    """Inicia o Agent Core; prepara MySQL e migra os JSONs em segundo plano."""
    global _agente
    if _agente is not None:
        return _agente
    from pathlib import Path
    from agente.adaptadores_yasm import criar_adaptadores
    from agente.nucleo import NucleoAgente
    from agente.percepcao import Percepcao
    from agente.integracao_aplicacoes.descoberta import descobrir_aplicacoes
    from agente.integracao_aplicacoes.estado import registrar_perceptores
    from agente.integracao_aplicacoes.ferramentas import registrar_ferramentas_aplicacoes
    from agente.planejamento import Planejador
    from infraestrutura.mysql_memoria import RepositorioMemoriaMySQL
    from infraestrutura.memoria_disponibilidade import MemoriaMySQLDisponivel

    repositorio = MemoriaMySQLDisponivel(RepositorioMemoriaMySQL(),
                                        Path(__file__).resolve().parent)
    ferramentas, verificador = criar_adaptadores()
    raiz_aplicacoes = Path(__file__).resolve().parent.parent / "applications"
    descoberta = descobrir_aplicacoes(raiz_aplicacoes)
    registrar_ferramentas_aplicacoes(ferramentas, verificador, descoberta, raiz_aplicacoes)
    percepcao = Percepcao()
    registrar_perceptores(percepcao, descoberta)
    _agente = NucleoAgente(percepcao, repositorio, _raciocinio_agente,
                          Planejador(ferramentas), ferramentas, verificador)
    return _agente


def inicializar_conversacao():
    global _conversacao
    if _conversacao is None:
        from agente.conversacao import ServicoConversacao
        from infraestrutura.dialogo_groq import DialogoGroq
        preferencias = memoria.get("preferencias", {})
        iniciais = {}
        if preferencias.get("tamanho_respostas"):
            iniciais["tamanho_respostas"] = preferencias["tamanho_respostas"]
        if preferencias.get("personalidade"):
            iniciais["tom"] = preferencias["personalidade"]
        _conversacao = ServicoConversacao(inicializar_agente().memoria, DialogoGroq(),
                                        historico=lambda: memoria.get("historico", []),
                                        preferencias_iniciais=iniciais)
        if memoria.get("configuracao", {}).get("concluida"):
            _conversacao.aplicar_preferencias(preferencias)
    return _conversacao


def inicializar_motor_decisao():
    """Usa o modelo local treinado e mantém o diálogo externo como recurso opcional."""
    global _motor_decisao
    if _motor_decisao is None:
        from agente.modelo_treinavel import ModeloIntencoesLocal, MotorDecisaoHibrido
        from infraestrutura.dialogo_groq import DialogoGroq
        caminho = Path(__file__).resolve().parent / "modelos" / "intencoes_local.json"
        try:
            local = ModeloIntencoesLocal.carregar(caminho)
        except (OSError, ValueError, KeyError, TypeError) as erro:
            local = None
            if DEBUG:
                logging.getLogger("yasm.agente").debug("[AGENTE] Modelo local indisponível: %s", erro)
        _motor_decisao = MotorDecisaoHibrido(local, DialogoGroq())
    return _motor_decisao

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

def _processar_comando(texto):
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
            usar_corretor=False,
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

    # O Agent Core decide a via da interação. O dispatcher abaixo permanece
    # como adaptador das capacidades legadas aceitas pelo classificador.
    try:
        agente = inicializar_agente()
        nome_legado = interpretacao.nome if interpretacao else ""
        aceita_legado = interpretacao.aceita if interpretacao else False
        if nome_legado == "DESCONHECIDA" and memoria.get("estudo", {}).get("quiz_atual") is not None:
            nome_legado, aceita_legado = "QUIZ_PENDENTE", True
        elif getattr(comandos, "musica_pendente", lambda: False)():
            nome_legado, aceita_legado = "MUSICA", True
        resposta_agente = agente.atender(
            texto_original, inicializar_conversacao,
            intencao_legada=(nome_legado, aceita_legado, interpretacao.parametros if interpretacao else {}),
            motor_decisao=inicializar_motor_decisao(), historico=memoria.get("historico", []),
            confirmacao_pendente=bool(_conversacao and _conversacao.confirmacao_pendente),
        )
        if resposta_agente is not None:
            return resposta_agente
    except Exception as erro:
        if DEBUG:
            print(f"[AGENTE] Falha ao decidir: {type(erro).__name__}: {erro}")
        return "Não consegui interpretar com segurança. Pode reformular o pedido?"

    # ========================================================
    # FALLBACK SE O INTENT FALHAR
    # ========================================================

    if interpretacao is None:
        return _responder_conversa(texto_original)

    if interpretacao.nome != "DESCONHECIDA" and not interpretacao.aceita:
        if interpretacao.nome in {"ABRIR_APLICATIVO", "FECHAR_APLICATIVO", "ENCERRAR", "ATALHO_JAVA", "ATALHO_PROGRAMAR", "ATALHO_BANCO"}:
            return "Nao tenho certeza do comando. Pode repetir de outra forma?"
        return _responder_conversa(texto_original)

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

                if interpretacao.nome == "ABRIR_APLICATIVO" and _agente is not None:
                    from agente.modelos import Objetivo
                    comando = Objetivo(texto_original, tipo="comando",
                                       parametros={"aplicativo": aplicativo})
                    return _agente.executar(texto_original, comando).mensagem

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

    return _responder_conversa(texto_original)


def _responder_conversa(texto):
    try:
        agente = inicializar_agente()
        return agente.conversar(texto, inicializar_conversacao())
    except Exception as erro:
        if DEBUG:
            print(f"[AGENTE] Conversa indisponível: {type(erro).__name__}: {erro}")
        return falas.escolher("nao_entendi")


# ============================================================
# MODO DE CONVERSA
# ============================================================

def processar_comando(texto):
    """Serializa comandos da voz e da janela sobre o mesmo estado do agente."""
    with _trava_comandos:
        if str(texto or "").strip():
            registrar_historico("usuario", str(texto))
        resposta = _processar_comando(texto)
        if _agente is not None:
            _agente.concluir_legado(resposta)
        if resposta and resposta != "encerrar":
            registrar_historico("yasm", resposta)
        return resposta


def estado_atual() -> dict:
    """Expõe somente estados operacionais, sem conteúdo pessoal ou do objetivo."""
    return {"estado_agente": _agente.estado.status.value if _agente else "inicializando",
            "estado_voz": estados.estado.name.lower(),
            "falando": voz.falando(),
            "microfone": audio.estado_captura(),
            "tarefa_atual": _agente.estado.tarefa_atual if _agente else None,
            "processos": [dict(item) for item in _agente.estado.processos[-6:]] if _agente else []}


def ativacao_detectada():
    estados.mudar(Estado.PALAVRA_DE_ATIVACAO_DETECTADA)
    estados.mudar(Estado.ESCUTANDO_COMANDO)


def responder_voz(texto):
    estados.mudar(Estado.RESPONDENDO)
    inicio = time.monotonic()
    try:
        return voz.falar(texto)
    finally:
        metricas.medir("resposta_voz", time.monotonic() - inicio)
        estados.mudar(Estado.AGUARDANDO_CONTINUACAO)


def conversar(texto_inicial=None):
    if estados.estado == Estado.AGUARDANDO_ATIVACAO:
        ativacao_detectada()
    nome = configurar_usuario()
    if not remover_prefixo(texto_inicial or ""):
        texto_inicial = None
        responder_voz(falas.escolher("ouvindo_nome", nome=nome))
    inicio_modo = time.monotonic()
    try:
        while time.monotonic() - inicio_modo < TEMPO_MODO_CONVERSA:
            estados.mudar(Estado.ESCUTANDO_COMANDO)
            if texto_inicial:
                texto, texto_inicial = texto_inicial, None
            else:
                texto = audio.escutar(timeout=TEMPO_ESPERA_CONVERSA)
                resultado = audio.ultimo_resultado
                if not texto:
                    if resultado.status != "silencio":
                        mensagem = ("A frase ficou longa demais. Pode dividir o pedido?"
                                    if resultado.status == "frase_longa" else
                                    "Nao consegui entender. Pode repetir?")
                        responder_voz(mensagem)
                    return
                if resultado.id and not entregas.aceitar(resultado.id):
                    continue
            if normalizar(remover_prefixo(texto)) in {"cancelar", "cancela", "deixa pra la", "deixa para la"}:
                responder_voz("Tudo bem, cancelei.")
                return
            estados.mudar(Estado.PROCESSANDO_COMANDO)
            inicio = time.monotonic()
            resposta = processar_comando(texto)
            metricas.medir("interpretacao_e_execucao", time.monotonic() - inicio)
            if resposta == "encerrar":
                responder_voz(falas.escolher("despedida", nome=nome))
                raise SystemExit(0)
            if resposta:
                responder_voz(resposta)
            else:
                estados.mudar(Estado.AGUARDANDO_CONTINUACAO)
            inicio_modo = time.monotonic()
    finally:
        estados.mudar(Estado.AGUARDANDO_ATIVACAO)


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

        config_inicial.iniciar(agente=inicializar_agente(),
                             conversacao=inicializar_conversacao())

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

def _main(texto_inicial=None):

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

            texto = audio.aguardar_ativacao(ao_ativar=ativacao_detectada)

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

        except audio.FalhaCaptura:
            estados.mudar(Estado.RECUPERANDO_ERRO)
            print("[Audio] Microfone indisponivel apos recuperacao limitada. Reinicie a Yasm.")
            return 1

        except Exception as erro:

            print(
                "[Erro interno] "
                f"{type(erro).__name__}: {erro!r}"
            )

            if DEBUG:

                import traceback

                traceback.print_exc()

            return 1


def main(texto_inicial=None):
    global estados
    estados = MaquinaEstados()
    voz.aquecer_motor_em_segundo_plano()
    try:
        inicializar_agente()
    except Exception as erro:
        if DEBUG:
            print(f"[AGENTE] Memória MySQL indisponível: {type(erro).__name__}: {erro}")
    try:
        return _main(texto_inicial)
    finally:
        audio.encerrar()
        estados.mudar(Estado.ENCERRADO)


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Assistente de voz Yasm")
    parser.add_argument("--comando", help="Comando recebido pelo launcher")
    raise SystemExit(main(parser.parse_args().comando))
