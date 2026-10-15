import json
import os
import re
import speech_recognition as sr
import sounddevice as sd
import numpy as np
import subprocess
import sys
import time
import socket
import threading

from pathlib import Path

try:
    from vosk import KaldiRecognizer, Model, SetLogLevel
except ImportError:
    KaldiRecognizer = None
    Model = None
    SetLogLevel = None

from interface import status
from config_yasm import RECONHECIMENTO_ONLINE, MODELO_VOSK_DIR, TIMEOUT_INTERNET
from util_yasm import normalizar, VARIACOES_YASM


# ============================================================
# CONFIGURAÇÕES
# ============================================================

IDIOMA = "pt-BR"

TEMPO_MAXIMO_FRASE = 6

BASE = Path(__file__).resolve().parent

YASM = BASE / "yas.py"

SERVICO_VOZ = BASE / "servicos" / "voz_neural_server.py"

MODELO_VOSK = MODELO_VOSK_DIR

HOST = "127.0.0.1"

PORTA_STATUS = 45454


# ============================================================
# RECONHECEDOR DO LAUNCHER
# ============================================================

reconhecedor = sr.Recognizer()

reconhecedor.dynamic_energy_threshold = True
reconhecedor.energy_threshold = 250
reconhecedor.pause_threshold = 0.65
reconhecedor.phrase_threshold = 0.18
reconhecedor.non_speaking_duration = 0.35
reconhecedor.operation_timeout = TIMEOUT_INTERNET

modelo_vosk = None
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


def preparar_reconhecimento_offline():
    global modelo_vosk

    if Model is None:
        raise RuntimeError(
            "Vosk nao esta instalado neste Python. Execute pip install -r requirements.txt."
        )

    if not MODELO_VOSK.is_dir():
        raise RuntimeError(f"Modelo Vosk nao encontrado em {MODELO_VOSK}.")

    if SetLogLevel is not None:
        SetLogLevel(-1)

    modelo_vosk = Model(str(MODELO_VOSK))


def transcrever_offline(audio):
    if modelo_vosk is None:
        preparar_reconhecimento_offline()

    if modelo_vosk is None:
        raise RuntimeError("Reconhecimento offline nao foi inicializado.")

    motor = KaldiRecognizer(modelo_vosk, 16000)
    motor.SetWords(False)
    motor.AcceptWaveform(audio.get_raw_data(convert_rate=16000, convert_width=2))
    return str(json.loads(motor.FinalResult()).get("text", "")).strip()


def transcrever(audio):
    if RECONHECIMENTO_ONLINE:
        try:
            return reconhecedor.recognize_google(audio, language=IDIOMA).strip()
        except (sr.RequestError, OSError) as erro:
            print("Google indisponivel. Usando reconhecimento local:", erro)
        except sr.UnknownValueError:
            pass

    return transcrever_offline(audio)


# ============================================================
# MICROFONE DO LAUNCHER
# ============================================================

# Use sounddevice como no processo principal, sem abrir hardware na importacao.
microfone = None


def dispositivo_entrada():
    escolha = os.environ.get("YASM_AUDIO_DEVICE", "").strip()
    if escolha.isdigit():
        return int(escolha)
    return escolha or None


# ============================================================
# SERVIDOR DE STATUS
# ============================================================

servidor_status = None


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

    if microfone is not None:

        with microfone as fonte:

            print(
                "Calibrando microfone..."
            )

            print(
                "Fique em silêncio por 2 segundos."
            )

            reconhecedor.adjust_for_ambient_noise(
                fonte,
                duration=2
            )

        print(
            "Microfone calibrado."
        )

        return

    # --------------------------------------------------------
    # FALLBACK SOUNDDEVICE
    # --------------------------------------------------------

    print(
        "PyAudio não disponível."
    )

    print(
        "Tentando sounddevice..."
    )

    taxa = 16000

    duracao = 2

    gravacao = sd.rec(
        int(
            duracao * taxa
        ),
        samplerate=taxa,
        channels=1,
        dtype="int16",
        device=dispositivo_entrada(),
    )

    sd.wait()

    energia = float(
        np.sqrt(
            np.mean(
                np.square(
                    gravacao.astype(
                        np.float32
                    )
                )
            )
        )
    )

    reconhecedor.energy_threshold = max(
        120,
        int(
            energia * 3.2
        )
    )

    print(
        "Microfone calibrado."
    )


# ============================================================
# RECONHECIMENTO
# ============================================================

def escutar():

    while True:

        try:

            if microfone is not None:

                with microfone as fonte:

                    audio = reconhecedor.listen(
                        fonte,
                        timeout=None,
                        phrase_time_limit=(
                            TEMPO_MAXIMO_FRASE
                        )
                    )

            else:

                audio = gravar_sounddevice()

            texto = transcrever(audio)

            if not texto:
                raise sr.UnknownValueError()

            return (
                texto
                .lower()
                .strip()
            )

        except sr.UnknownValueError:

            continue

        except sr.RequestError as erro:

            print(
                "Erro no reconhecimento:",
                erro
            )

            time.sleep(1)

        except (OSError, RuntimeError, sd.PortAudioError) as erro:

            print(
                "Erro no microfone:",
                erro
            )

            time.sleep(1)


# ============================================================
# SOUNDDEVICE
# ============================================================

def gravar_sounddevice():

    taxa = 16000

    bloco = int(
        taxa * 0.1
    )

    limite_silencio = (
        reconhecedor.pause_threshold
    )

    limite_energia = max(
        160,
        int(
            reconhecedor.energy_threshold
            * 1.15
        )
    )

    pre_buffer = []

    blocos = []

    inicio_fala = None

    ultima_voz = None

    with sd.InputStream(
        samplerate=taxa,
        channels=1,
        dtype="int16",
        blocksize=bloco,
        device=dispositivo_entrada(),
    ) as stream:

        while True:

            dados, _ = stream.read(
                bloco
            )

            agora = time.monotonic()

            energia = float(
                np.sqrt(
                    np.mean(
                        np.square(
                            dados.astype(
                                np.float32
                            )
                        )
                    )
                )
            )

            # ------------------------------------------------
            # ESPERANDO FALA
            # ------------------------------------------------

            if inicio_fala is None:

                pre_buffer.append(
                    dados.copy()
                )

                if len(pre_buffer) > 4:

                    pre_buffer.pop(0)

            # ------------------------------------------------
            # DETECTOU VOZ
            # ------------------------------------------------

            if energia >= limite_energia:

                if inicio_fala is None:

                    inicio_fala = agora

                    blocos.extend(
                        pre_buffer[:-1]
                    )

                ultima_voz = agora

            # ------------------------------------------------
            # GRAVANDO
            # ------------------------------------------------

            if inicio_fala is not None:

                blocos.append(
                    dados.copy()
                )

                if (
                    ultima_voz is not None
                    and agora - ultima_voz
                    >= limite_silencio
                ):

                    break

            # ------------------------------------------------
            # FRASE MUITO LONGA
            # ------------------------------------------------

            if (
                inicio_fala is not None
                and agora - inicio_fala
                >= TEMPO_MAXIMO_FRASE
            ):

                break

    if not blocos:

        raise sr.UnknownValueError()

    audio = np.concatenate(
        blocos
    ).tobytes()

    return sr.AudioData(
        audio,
        taxa,
        2
    )


# ============================================================
# DETECTOR DE INICIALIZAÇÃO
# ============================================================

def deve_iniciar(texto):
    return bool(set(normalizar(texto).split()) & VARIACOES_YASM)


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
    global processo_voz, servidor_status
    processo_yasm = None
    processo_voz = None
    print("Launcher da Yasm iniciado.")
    try:
        # Reserve o status antes de abrir microfone ou iniciar outros processos.
        iniciar_servidor_status()
        if not RECONHECIMENTO_ONLINE:
            preparar_reconhecimento_offline()
        calibrar()
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
            status.iniciar()
            status.desligada()
        except Exception as erro:
            print("[Aviso] Falha no HUD:", erro)
        threading.Thread(
            target=monitorar_status, daemon=True, name="yasm-status-monitor",
        ).start()
        print("Estou aguardando voce chamar a Yasm.")
        while True:
            if processo_yasm is not None:
                if processo_yasm.poll() is None:
                    time.sleep(0.5)
                    continue
                print("Yasm encerrada. Aguardando novamente...")
                processo_yasm = None
                status.desligada()
            texto = escutar()
            if not texto:
                continue
            print(f"Voce: {texto}")
            if deve_encerrar(texto):
                break
            if deve_iniciar(texto):
                status.desligada()
                processo_yasm = subprocess.Popen(
                    [sys.executable, str(YASM), "--comando", comando_inicial(texto)],
                    cwd=str(BASE),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as erro:
        print(f"[Erro] Nao foi possivel executar a Yasm: {type(erro).__name__}: {erro}")
        return 1
    finally:
        encerrar_processo(processo_yasm)
        encerrar_processo(processo_voz)
        if servidor_status is not None:
            servidor_status.close()
            servidor_status = None
        status.fechar()
        print("Launcher finalizado.")


if __name__ == "__main__":
    raise SystemExit(main())
