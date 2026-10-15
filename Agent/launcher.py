import json
import errno
import os
import re
from http.client import HTTPConnection, HTTPException
import speech_recognition as sr
import sounddevice as sd
import numpy as np
import subprocess
import sys
import time
import socket
import threading

from pathlib import Path

from interface import status
from servicos.comandos_workspace import PORTA as PORTA_COMANDOS
from config_yasm import RECONHECIMENTO_ONLINE
from util_yasm import normalizar
from ativacao_yasm import chamada_exata
# Serviço de voz é aquecido pelo launcher, sem uma segunda cópia por importação.
os.environ["YASM_VOICE_SERVER"] = "1"
import audio_yasm as audio


# ============================================================
# CONFIGURAÇÕES
# ============================================================

IDIOMA = "pt-BR"

TEMPO_MAXIMO_FRASE = 6

BASE = Path(__file__).resolve().parent

YASM = BASE / "yas.py"

SERVICO_VOZ = BASE / "servicos" / "voz_neural_server.py"


HOST = "127.0.0.1"

PORTA_STATUS = 45454


# ============================================================
# RECONHECEDOR DO LAUNCHER
# ============================================================

processo_voz = None


def aguardar_servico_voz(timeout=35.0):
    inicio = time.monotonic()
    mensagem = json.dumps({"acao": "ping"}).encode("utf-8") + b"\n"

    while time.monotonic() - inicio < timeout:
        if processo_voz is not None and processo_voz.poll() is not None:
            return False

        try:
            with socket.create_connection(("127.0.0.1", 45455), timeout=0.5) as cliente:
                cliente.settimeout(2.0)
                cliente.sendall(mensagem)
                with cliente.makefile("rb") as resposta_stream:
                    resposta = resposta_stream.readline(4096)
                if resposta and json.loads(resposta.decode("utf-8")).get("pronto"):
                    return True
        except (OSError, ValueError, json.JSONDecodeError):
            time.sleep(0.2)

    return False


# ============================================================
# SERVIDOR DE STATUS
# ============================================================

servidor_status = None
servidor_comandos = None


def iniciar_interface_workspace():
    """Mantém o mesmo processador da voz disponível na janela gráfica."""
    global servidor_comandos
    from servicos.comandos_workspace import criar_servidor_comandos
    from interface.janela_workspace import abrir_janela

    def processar(texto: str) -> dict:
        import yas
        from agente.integracao_aplicacoes.abertura import abertura_no_workspace
        objetivo = yas._raciocinio_agente.identificar(texto)
        with abertura_no_workspace():
            resposta = yas.processar_comando(texto)
        falar_resposta_workspace(resposta, yas.voz.falar)
        dados = {"resposta": resposta or "Não recebi uma resposta verificável para esse comando."}
        if (objetivo and objetivo.parametros.get("tipo") == "abrir_aplicacao_ink"
                and isinstance(resposta, str) and resposta.startswith("Abri ")):
            aplicacao = objetivo.parametros.get("aplicacao")
            if aplicacao != "workspace-os":
                dados["aplicacao"] = aplicacao
        elif (objetivo and objetivo.parametros.get("tipo") == "exportar_contexto_projeto_ink"
              and yas._agente is not None
              and yas._agente.estado.aplicativo_ativo == "project-reader"):
            dados["aplicacao"] = "project-reader"
        return dados

    def estado():
        import yas
        return yas.estado_atual()

    servidor_comandos = criar_servidor_comandos(processar, estado=estado)
    threading.Thread(target=servidor_comandos.serve_forever, daemon=True,
                     name="yasm-workspace-comandos").start()

    def abrir():
        try:
            if not abrir_janela():
                print("[Aviso] Workspace OS não abriu; comandos de voz continuam disponíveis.")
        except Exception as erro:
            print(f"[Aviso] Janela da Yasmin indisponível: {type(erro).__name__}: {erro}")

    threading.Thread(target=abrir, daemon=True, name="yasm-workspace-janela").start()


def falar_resposta_workspace(resposta: str | None, falar) -> None:
    """Reproduz respostas da janela sem atrasar a entrega do texto."""
    if (os.environ.get("YASM_VOZ_WORKSPACE", "1") == "0"
            or not isinstance(resposta, str) or not resposta.strip()
            or resposta == "encerrar"):
        return
    trecho = resposta if len(resposta) <= 500 else "Concluí a tarefa. Veja o resultado na conversa."

    def executar() -> None:
        try:
            falar(trecho)
        except Exception as erro:
            print(f"[Aviso] Resposta por voz indisponível: {type(erro).__name__}: {erro}")

    threading.Thread(target=executar, daemon=True, name="yasm-workspace-fala").start()


def iniciar_servidor_status():

    global servidor_status

    servidor = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM
    )

    try:
        servidor.bind((HOST, PORTA_STATUS))
        servidor.settimeout(0.5)
    except OSError:
        servidor.close()
        raise
    servidor_status = servidor


def instancia_yasmin_ativa(porta: int = PORTA_COMANDOS) -> bool:
    """Confirma que a porta ocupada pertence ao canal local da Yasmin."""
    conexao = HTTPConnection(HOST, porta, timeout=0.5)
    try:
        conexao.request("GET", "/health")
        resposta = conexao.getresponse()
        if resposta.status != 200:
            return False
        dados = json.loads(resposta.read(4096).decode("utf-8"))
        return (isinstance(dados, dict) and dados.get("ok") is True
                and dados.get("status") == "pronta"
                and "estado_agente" in dados and "estado_voz" in dados)
    except (OSError, HTTPException, ValueError, UnicodeError):
        return False
    finally:
        conexao.close()


def monitorar_status():

    while True:

        if servidor_status is None:
            time.sleep(0.1)
            continue

        try:

            dados, _ = servidor_status.recvfrom(
                1024
            )

            mensagem = (
                dados
                .decode(
                    "utf-8",
                    errors="ignore"
                )
                .strip()
                .upper()
            )

            if mensagem == "ONLINE":

                try:
                    status.funcionando()
                except Exception:
                    pass

            elif mensagem == "OFFLINE":

                try:
                    status.desligada()
                except Exception:
                    pass

        except socket.timeout:

            continue

        except OSError:

            break

        except Exception:

            continue


# ============================================================
# CALIBRAÇÃO
# ============================================================

def calibrar():
    audio.preparar_reconhecimento()
    audio.calibrar_sounddevice()


def escutar():
    import yas
    return audio.aguardar_ativacao(ao_ativar=yas.ativacao_detectada)


def deve_iniciar(texto):
    return chamada_exata(texto)


# ============================================================
# DETECTOR DE ENCERRAMENTO DO LAUNCHER
# ============================================================

def deve_encerrar(texto):

    texto = texto.lower().strip()

    comandos = (
        "fechar launcher",
        "feche o launcher",
        "parar launcher",
        "pare o launcher",
        "sair do launcher",
        "encerrar launcher",
    )

    return any(
        comando in texto
        for comando in comandos
    )


def encerrar_processo(processo):
    if processo is None or processo.poll() is not None:
        return
    try:
        processo.terminate()
        processo.wait(timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        try:
            processo.kill()
            processo.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            pass


def comando_inicial(texto):
    # Retire apenas o pedido de ativacao, mantendo uma eventual pergunta.
    return re.sub(
        r"^(?:iniciar|inicia|ligar|liga|abrir|abre|ativar|ativa)\s+",
        "", str(texto).strip(), flags=re.IGNORECASE,
    )


def main():
    global processo_voz, servidor_status, servidor_comandos
    processo_yasm = None
    processo_voz = None
    print("Launcher da Yasm iniciado.")
    try:
        # Reserve o status antes de abrir microfone ou iniciar outros processos.
        try:
            iniciar_servidor_status()
        except OSError as erro:
            porta_ocupada = (getattr(erro, "winerror", None) == 10048
                             or erro.errno in {errno.EADDRINUSE, 10048})
            if not porta_ocupada:
                raise
            if not instancia_yasmin_ativa():
                print(f"[Erro] A porta local {PORTA_STATUS} esta ocupada por outro processo.")
                return 1
            print("A Yasmin ja esta em execucao. Abrindo o Workspace existente.")
            from interface.janela_workspace import abrir_janela
            if not abrir_janela():
                print("[Aviso] A Yasmin esta ativa, mas nao consegui abrir a janela.")
                return 1
            return 0
        try:
            iniciar_interface_workspace()
        except Exception as erro:
            print(f"[Aviso] Canal de comandos do Workspace indisponível: {type(erro).__name__}: {erro}")
        try:
            calibrar()
            microfone_pronto = True
        except Exception as erro:
            microfone_pronto = False
            print(f"[Aviso] Microfone indisponível; a janela continua ativa: {type(erro).__name__}: {erro}")
        if not aguardar_servico_voz(timeout=0.6):
            processo_voz = subprocess.Popen(
                [sys.executable, "-m", "servicos.voz_neural_server"],
                cwd=str(BASE), stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            print("Preparando voz neural em segundo plano.")
            if not aguardar_servico_voz():
                print("[Aviso] Voz neural indisponivel; usando a voz de reserva.")
        try:
            if os.environ.get("YASM_HUD_LEGADO") == "1":
                status.iniciar()
            status.desligada()
        except Exception as erro:
            print("[Aviso] Falha no HUD:", erro)
        threading.Thread(
            target=monitorar_status, daemon=True, name="yasm-status-monitor",
        ).start()
        print("Estou aguardando voce chamar a Yasm.")
        while True:
            if not microfone_pronto:
                time.sleep(5)
                try:
                    calibrar()
                    microfone_pronto = True
                    print("Microfone reconectado.")
                except Exception:
                    continue
            if processo_yasm is not None:
                if processo_yasm.poll() is None:
                    time.sleep(0.5)
                    continue
                print("Yasm encerrada. Aguardando novamente...")
                processo_yasm = None
                status.desligada()
            try:
                texto = escutar()
            except Exception as erro:
                microfone_pronto = False
                print(f"[Aviso] Captação de voz interrompida; comandos pela janela continuam disponíveis: {type(erro).__name__}: {erro}")
                continue
            if not texto:
                continue
            if deve_encerrar(texto):
                break
            if deve_iniciar(texto):
                status.desligada()
                import yas
                status.funcionando()
                yas.executar_configuracao_inicial()
                try:
                    yas.conversar(comando_inicial(texto))
                except SystemExit:
                    status.desligada()
                finally:
                    yas.estados.mudar(yas.Estado.AGUARDANDO_ATIVACAO)

        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as erro:
        print(f"[Erro] Nao foi possivel executar a Yasm: {type(erro).__name__}: {erro}")
        return 1
    finally:
        audio.encerrar()
        encerrar_processo(processo_yasm)
        encerrar_processo(processo_voz)
        if servidor_status is not None:
            servidor_status.close()
            servidor_status = None
        if servidor_comandos is not None:
            servidor_comandos.shutdown()
            servidor_comandos.server_close()
            servidor_comandos = None
        status.fechar()
        print("Launcher finalizado.")


if __name__ == "__main__":
    raise SystemExit(main())
