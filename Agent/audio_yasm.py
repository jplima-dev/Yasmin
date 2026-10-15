import json
import os
import time
from collections import deque
from dataclasses import dataclass
from itertools import count
import socket

from captura_voz import CapturaContinua, FalhaCaptura
from pipeline_voz import Segmentador, metricas
from config_yasm import (ASR_MOTOR, ASR_FALLBACK, WAKE_MOTOR, VAD_MOTOR, SILENCIO_COMANDO, SILENCIO_CURTO,
                         LOG_TRANSCRICOES, REDUZIR_RUIDO, AUTO_GAIN)

import numpy as np
import sounddevice as sd
import speech_recognition as sr

try:
    from vosk import KaldiRecognizer, Model, SetLogLevel
except (ImportError, OSError):
    KaldiRecognizer = None
    Model = None
    SetLogLevel = None

from config_yasm import (
    TEMPO_MAXIMO_FRASE,
    IDIOMA,
    DEBUG,
    MODELO_VOSK_DIR,
    RECONHECIMENTO_ONLINE,
    TIMEOUT_INTERNET,
)
import voz_yasm as voz


# ============================================================
# AUDIO / RECONHECIMENTO LOCAL
# ============================================================
#
# Pipeline:
#   microfone -> VAD -> segmento PCM -> Google Speech (padrao)
#
# A escala interna de energia e sempre equivalente a int16.
# Isso evita o bug antigo em que blocos int16 eram multiplicados
# por 32768 de novo e pareciam absurdamente altos.

TAXA = 16000
CANAL = 1

BLOCO_MS = 20
BLOCO = int(TAXA * BLOCO_MS / 1000)

PREBUFFER_MS = 700
PREBUFFER_BLOCOS = max(1, int(PREBUFFER_MS / BLOCO_MS))

INICIO_MINIMO_MS = 80
INICIO_BLOCOS = max(1, int(INICIO_MINIMO_MS / BLOCO_MS))

SILENCIO_FIM = 0.55
MIN_DURACAO_AUDIO = 0.22

FFT_MS = 32
FFT_SIZE = int(TAXA * FFT_MS / 1000)
HOP = FFT_SIZE // 2

VOICE_LOW = 120.0
VOICE_HIGH = 3800.0
FILTER_LOW = 80.0
FILTER_HIGH = 7600.0

NOISE_SUBTRACTION = 1.10
NOISE_FLOOR = 0.055

AGC_TARGET_RMS = 0.07
AGC_MAX = 4.0

global_noise_rms = 30.0
global_noise_p90 = 45.0
global_noise_p95 = 60.0
global_start_threshold = 110.0
global_continue_threshold = 65.0
global_noise_spectrum = None
_modelo_vosk = None
_aviso_modelo = False


def _dispositivo_entrada():
    escolha = os.environ.get("YASM_AUDIO_DEVICE", "").strip()

    if not escolha:
        return None

    if escolha.isdigit():
        return int(escolha)

    escolha_n = escolha.casefold()

    try:
        dispositivos = sd.query_devices()
    except Exception as erro:
        raise FalhaCaptura("Nao foi possivel enumerar microfones") from erro

    for indice, dispositivo in enumerate(dispositivos):
        nome = str(dispositivo.get("name", ""))
        canais = int(dispositivo.get("max_input_channels", 0) or 0)

        if canais > 0 and escolha_n in nome.casefold():
            return indice

    raise FalhaCaptura(f"Microfone configurado nao encontrado: {escolha}")


def diagnostico_audio():
    try:
        if _captura is not None and _captura.stream is not None:
            nome = sd.query_devices(_captura.dispositivo).get("name", "desconhecido")
            return f"microfone ativo: {nome} ({_captura.taxa_entrada} Hz)"
        dispositivo = _dispositivo_entrada()
        if dispositivo is None:
            padrao = sd.query_devices(kind="input")
            return f"microfone padrao: {padrao.get('name', 'desconhecido')}"

        escolhido = sd.query_devices(dispositivo)
        return f"microfone selecionado: {escolhido.get('name', dispositivo)}"
    except Exception as erro:
        return f"diagnostico indisponivel: {type(erro).__name__}"


def estado_captura():
    """Diagnóstico operacional resumido para a janela, sem amostras de áudio."""
    return {"disponivel": _captura is not None and _captura.stream is not None,
            "erro": _erro_captura}


def _candidatos_captura():
    """Tenta o padrão e os outros dispositivos reais em 16 kHz ou taxa nativa."""
    escolhido = _dispositivo_entrada()
    try:
        dispositivos = sd.query_devices()
    except Exception as erro:
        raise FalhaCaptura("Nao foi possivel consultar dispositivos de entrada") from erro
    try:
        padrao = int(sd.default.device[0])
    except (IndexError, TypeError, ValueError, sd.PortAudioError):
        padrao = -1
    escolha = os.environ.get("YASM_AUDIO_DEVICE", "").strip()
    if escolha and not escolha.isdigit():
        indices = [i for i, item in enumerate(dispositivos)
                   if escolha.casefold() in str(item.get("name", "")).casefold()]
    elif escolhido is not None:
        indices = [escolhido]
    else:
        indices = [padrao] + [i for i in range(len(dispositivos)) if i != padrao]
    for indice in indices:
        if not isinstance(indice, int) or not 0 <= indice < len(dispositivos):
            continue
        dispositivo = dispositivos[indice]
        if int(dispositivo.get("max_input_channels", 0) or 0) < 1:
            continue
        taxas = (TAXA, int(dispositivo.get("default_samplerate") or TAXA))
        for taxa in dict.fromkeys(taxas):
            if taxa > 0:
                yield indice, taxa


def _audio_float(samples):
    origem = np.asarray(samples)
    audio = origem.astype(np.float32).reshape(-1)

    if audio.size == 0:
        return audio

    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
    # A amplitude nao identifica o formato: silencio int16 pode conter apenas
    # -1, 0 e 1. Tratar esses valores como float amplifica o ruido 32768 vezes.
    if np.issubdtype(origem.dtype, np.integer):
        limites = np.iinfo(origem.dtype)
        if limites.min == 0:
            centro = (limites.max + 1) / 2.0
            audio = (audio - centro) / centro
        else:
            audio = audio / float(-limites.min)
    elif float(np.max(np.abs(audio))) > 2.0:
        audio = audio / 32768.0

    audio = audio - float(np.mean(audio))
    return np.clip(audio, -1.0, 1.0)


def _rms(samples):
    audio = _audio_float(samples)

    if audio.size == 0:
        return 0.0

    return float(np.sqrt(np.mean(audio * audio)) * 32768.0)


def _spectral_features(samples):
    audio = _audio_float(samples)

    if audio.size == 0:
        return {
            "rms": 0.0,
            "voice_ratio": 0.0,
            "low_ratio": 0.0,
            "zcr": 0.0,
            "flatness": 1.0,
        }

    if audio.size < BLOCO:
        audio = np.pad(audio, (0, BLOCO - audio.size))

    janela = np.hanning(audio.size).astype(np.float32)
    espectro = np.fft.rfft(audio * janela)
    potencia = np.abs(espectro) ** 2
    total = float(np.sum(potencia)) + 1e-12
    freqs = np.fft.rfftfreq(audio.size, 1.0 / TAXA)

    faixa_voz = (freqs >= VOICE_LOW) & (freqs <= VOICE_HIGH)
    faixa_baixa = freqs < 90.0

    voice_ratio = float(np.sum(potencia[faixa_voz]) / total)
    low_ratio = float(np.sum(potencia[faixa_baixa]) / total)
    zcr = float(np.mean(np.abs(np.diff(np.signbit(audio)))))
    magnitude = np.sqrt(potencia + 1e-12)
    flatness = float(
        np.exp(np.mean(np.log(magnitude + 1e-12)))
        / (np.mean(magnitude) + 1e-12)
    )

    return {
        "rms": _rms(audio),
        "voice_ratio": voice_ratio,
        "low_ratio": low_ratio,
        "zcr": zcr,
        "flatness": flatness,
    }


def _parece_fala(samples, energia, threshold, *, iniciando):
    features = _spectral_features(samples)
    ratio_voz = features["voice_ratio"]
    ratio_baixo = features["low_ratio"]
    zcr = features["zcr"]
    flatness = features["flatness"]

    # Ruido de mesa, vento e pancadas costumam ter muita energia baixa.
    if ratio_baixo > 0.72 and ratio_voz < 0.34:
        return False

    # Chiado e ruido branco sao espalhados demais no espectro.
    if flatness > 0.38 and ratio_voz < 0.66:
        return False

    # Voz raramente cruza zero tanto quanto ruido eletrico/vento forte.
    if zcr > 0.34 and ratio_voz < 0.70:
        return False

    if energia >= threshold and ratio_voz >= 0.25:
        return True

    if energia >= threshold * 1.55 and ratio_voz >= 0.16:
        return True

    # Voz muito baixa, mas com assinatura bem vocal.
    if iniciando and energia >= max(18.0, global_noise_rms * 1.45) and ratio_voz >= 0.48:
        return True

    if not iniciando and energia >= max(10.0, global_noise_rms * 0.95) and ratio_voz >= 0.36:
        return True

    return False


def _perfil_espectral_ruido(samples):
    audio = _audio_float(samples)

    if audio.size < FFT_SIZE:
        return None

    janela = np.hanning(FFT_SIZE).astype(np.float32)
    espectros = []

    for inicio in range(0, len(audio) - FFT_SIZE + 1, HOP):
        frame = audio[inicio:inicio + FFT_SIZE]
        espectros.append(np.abs(np.fft.rfft(frame * janela)))

    if not espectros:
        return None

    return np.median(np.asarray(espectros), axis=0).astype(np.float32)


def calibrar_sounddevice(duracao=2.0):
    """Mede o ambiente e ajusta o VAD para o ruido atual."""
    global global_noise_rms
    global global_noise_p90
    global global_noise_p95
    global global_start_threshold
    global global_continue_threshold
    global global_noise_spectrum

    voz.aguardar_microfone()
    print("Yasm: Calibrando meu microfone. Fique em silencio por dois segundos.")
    captura = obter_captura()
    captura.descartar()
    blocos = [captura.ler() for _ in range(max(1, round(duracao * TAXA / BLOCO)))]
    samples = _audio_float(np.frombuffer(b"".join(blocos), dtype="<i2"))

    if samples.size == 0:
        global_noise_rms = 30.0
        global_noise_p90 = 45.0
        global_noise_p95 = 60.0
        global_start_threshold = 110.0
        global_continue_threshold = 65.0
        global_noise_spectrum = None
        return

    janela = max(1, BLOCO)
    rms_blocos = []

    for inicio in range(0, len(samples) - janela + 1, janela):
        rms_blocos.append(_rms(samples[inicio:inicio + janela]))

    if not rms_blocos:
        rms_blocos = [_rms(samples)]

    global_noise_rms = max(1.0, float(np.percentile(rms_blocos, 50)))
    global_noise_p90 = max(global_noise_rms, float(np.percentile(rms_blocos, 90)))
    global_noise_p95 = max(global_noise_p90, float(np.percentile(rms_blocos, 95)))

    # Inicio de fala: acima do ruido medio e tambem do ruido de pico.
    # Em silencio real ainda aceitamos voz baixa.
    global_start_threshold = max(
        18.0,
        global_noise_rms * 3.2,
        global_noise_p90 * 1.85,
        global_noise_p95 * 1.35,
    )

    global_continue_threshold = max(
        10.0,
        global_noise_rms * 1.65,
        global_noise_p90 * 1.05,
    )

    global_noise_spectrum = _perfil_espectral_ruido(samples)

    if DEBUG:
        print(
            "[Audio] ruido="
            f"{global_noise_rms:.1f} p90={global_noise_p90:.1f} "
            f"p95={global_noise_p95:.1f} inicio={global_start_threshold:.1f} "
            f"continua={global_continue_threshold:.1f} "
            f"perfil={'sim' if global_noise_spectrum is not None else 'nao'}"
        )


def _normalizar_audio(blocos):
    if not blocos:
        return np.empty(0, dtype=np.int16)

    audio = _audio_float(np.concatenate(blocos))

    if audio.size == 0:
        return np.empty(0, dtype=np.int16)

    rms = float(np.sqrt(np.mean(audio * audio)))

    if rms > 0:
        ganho = min(AGC_MAX, max(1.0, AGC_TARGET_RMS / rms))
        audio *= ganho

    pico = float(np.max(np.abs(audio))) if audio.size else 0.0

    if pico > 0.97:
        audio *= 0.92 / pico

    return np.clip(audio * 32768.0, -32768, 32767).astype(np.int16)


def _remover_ruido(audio_int16):
    """Reduz ruido estacionario e corta frequencias fora da voz."""
    global global_noise_spectrum

    audio = _audio_float(audio_int16)

    if audio.size < FFT_SIZE:
        return np.asarray(audio_int16, dtype=np.int16)

    janela = np.hanning(FFT_SIZE).astype(np.float32)
    total_frames = int(np.ceil(max(1, audio.size - FFT_SIZE) / HOP)) + 1
    tamanho_saida = (total_frames - 1) * HOP + FFT_SIZE
    audio_padded = np.pad(audio, (0, max(0, tamanho_saida - audio.size)))

    saida = np.zeros(tamanho_saida, dtype=np.float32)
    peso = np.zeros(tamanho_saida, dtype=np.float32)

    freqs = np.fft.rfftfreq(FFT_SIZE, 1.0 / TAXA)
    faixa = (freqs >= FILTER_LOW) & (freqs <= FILTER_HIGH)

    noise = global_noise_spectrum

    if noise is None or len(noise) != len(freqs):
        noise = np.zeros_like(freqs, dtype=np.float32)
    else:
        noise = noise.astype(np.float32)

    for indice in range(total_frames):
        inicio = indice * HOP
        frame = audio_padded[inicio:inicio + FFT_SIZE]
        frame = frame - float(np.mean(frame))

        espectro = np.fft.rfft(frame * janela)
        magnitude = np.abs(espectro)
        fase = np.angle(espectro)

        limpo = np.maximum(
            magnitude - (NOISE_SUBTRACTION * noise),
            NOISE_FLOOR * np.maximum(noise, 1e-8),
        )

        limpo = np.where(faixa, limpo, limpo * 0.10)

        reconstruido = np.fft.irfft(limpo * np.exp(1j * fase), n=FFT_SIZE)

        saida[inicio:inicio + FFT_SIZE] += reconstruido * janela
        peso[inicio:inicio + FFT_SIZE] += janela * janela

    mascara = peso > 1e-6
    saida[mascara] /= peso[mascara]
    saida[~mascara] = 0.0
    saida = saida[:audio.size]

    # Noise gate suave em trechos quase silenciosos.
    rms_saida = _rms(saida)
    if rms_saida < max(6.0, global_noise_rms * 0.40):
        saida *= 0.35

    pico = float(np.max(np.abs(saida))) if saida.size else 0.0

    if pico > 0:
        ganho = min(AGC_MAX, 0.90 / pico)
        saida *= ganho

    return np.clip(saida * 32768.0, -32768, 32767).astype(np.int16)


_captura = None
_erro_captura = None
_detector = None
_preparado = False
_vad = None
_whisper = None
_ids = count(1)


@dataclass(frozen=True)
class ResultadoEscuta:
    id: int = 0
    texto: str = ""
    status: str = "silencio"
    motor: str = ""
    fallback: bool = False


ultimo_resultado = ResultadoEscuta()


class Vad:
    def __init__(self):
        self.motor = None
        if VAD_MOTOR not in {"auto", "webrtc", "energia"}:
            raise ValueError("YASM_VAD deve ser auto, webrtc ou energia")
        if VAD_MOTOR != "energia":
            try:
                import webrtcvad
                self.motor = webrtcvad.Vad(1)
            except ImportError:
                if VAD_MOTOR == "webrtc":
                    raise RuntimeError("Instale webrtcvad-wheels neste Python")
                print("[Audio] WebRTC indisponivel; VAD espectral de reserva")

    def fala(self, pcm, iniciando=False):
        if self.motor is not None and self.motor.is_speech(pcm, TAXA):
            return True
        # A analise espectral mais cara so e executada quando WebRTC rejeita.
        amostras = np.frombuffer(pcm, dtype="<i2")
        limiar = global_start_threshold if iniciando else global_continue_threshold
        return _parece_fala(amostras, _rms(amostras), limiar, iniciando=iniciando)


def obter_captura():
    global _captura, _erro_captura
    if _captura is not None:
        _captura.iniciar()
        return _captura
    erros = []
    for dispositivo, taxa in _candidatos_captura():
        candidata = CapturaContinua(dispositivo, voz.microfone_bloqueado,
                                    taxa_entrada=taxa)
        try:
            candidata.iniciar()
        except FalhaCaptura as erro:
            erros.append((dispositivo, taxa, erro))
            if DEBUG:
                print(f"[Audio] Entrada {dispositivo}/{taxa} Hz: {type(erro.__cause__).__name__}")
            continue
        _captura = candidata
        _erro_captura = None
        if DEBUG:
            print(f"[Audio] Microfone {dispositivo} ativo em {taxa} Hz")
        return candidata
    detalhe = str(erros[0][2]).split(" [PaErrorCode", 1)[0] if erros else "nenhum dispositivo de entrada encontrado"
    _erro_captura = (f"Nenhum microfone pôde ser aberto ({len(erros)} combinações testadas). "
                     f"Primeira falha: {detalhe}. "
                     "Confira a conexão, a permissão de microfone para aplicativos de desktop "
                     "e YASM_AUDIO_DEVICE.")
    raise FalhaCaptura(_erro_captura)


def fechar_captura():
    global _captura
    captura, _captura = _captura, None
    if captura is not None:
        metricas.contar("blocos_perdidos", captura.perdidos)
        captura.fechar()


def encerrar():
    global _detector, _preparado
    try:
        fechar_captura()
    finally:
        detector, _detector = _detector, None
        _preparado = False
        if detector is not None:
            detector.fechar()


def _vad_atual():
    global _vad
    if _vad is None:
        _vad = Vad()
    return _vad


def _capturar_segmento(timeout, frase_maxima, iniciais=()):
    captura = obter_captura()
    if not iniciais:
        voz.aguardar_microfone()
        captura.descartar()
    segmentador = Segmentador(maximo=frase_maxima, silencio=SILENCIO_COMANDO,
                             silencio_curto=SILENCIO_CURTO, pre_ms=300)
    vad = _vad_atual()
    inicio = time.monotonic()
    pendentes = deque(iniciais)
    while True:
        pcm = pendentes.popleft() if pendentes else captura.ler()
        amostras = np.frombuffer(pcm, dtype="<i2")
        if np.any(np.abs(amostras.astype(np.int32)) >= 32760):
            metricas.contar("blocos_clipping")
        segmento = segmentador.alimentar(pcm, vad.fala(pcm, not segmentador.ativo))
        if segmento is not None:
            metricas.medir("captura", time.monotonic() - inicio)
            metricas.medir("audio", segmento.duracao)
            metricas.medir("fim_fala", segmentador.pausa)
            metricas.fim_fala = time.monotonic() - segmentador.pausa
            if segmento.motivo == "limite":
                raise FraseLonga("Frase excedeu limite; nao executar comando parcial")
            if segmento.fala_segundos < segmentador.minimo:
                raise sr.UnknownValueError()
            return segmento.pcm
        if not segmentador.ativo and timeout is not None and time.monotonic() - inicio >= timeout:
            raise sr.WaitTimeoutError()


class FraseLonga(ValueError):
    pass


def gravar_com_sounddevice(timeout=None, frase_maxima=TEMPO_MAXIMO_FRASE, *, iniciais=()):
    pcm = _capturar_segmento(timeout, frase_maxima, iniciais)
    if REDUZIR_RUIDO:
        pcm = _remover_ruido(np.frombuffer(pcm, dtype="<i2")).tobytes()
    if AUTO_GAIN:
        pcm = _normalizar_audio([np.frombuffer(pcm, dtype="<i2")]).tobytes()
    return sr.AudioData(pcm, TAXA, 2)


def recuperar_captura(operacao):
    for tentativa in range(3):
        try:
            return operacao()
        except (FalhaCaptura, sd.PortAudioError) as erro:
            metricas.contar("falhas_captura")
            fechar_captura()
            if tentativa == 2:
                raise FalhaCaptura(f"Microfone falhou apos tres tentativas: {erro}") from erro
            time.sleep(0.25 * 2 ** tentativa)
            metricas.contar("tentativas_recuperacao")


def aguardar_ativacao(ao_ativar=None):
    """Reconhece a chamada pelo motor configurado e devolve o comando."""
    from ativacao_yasm import chamada_exata, remover_prefixo

    if WAKE_MOTOR == "google":
        if not _preparado:
            preparar_reconhecimento()

        def aguardar_google():
            falhas_rede = 0
            while True:
                try:
                    audio = gravar_com_sounddevice(timeout=None)
                except (sr.UnknownValueError, FraseLonga):
                    continue
                resultado = transcrever_audio(audio, motor="google", usar_reserva=False)
                if resultado.status in {"timeout", "servico_indisponivel"}:
                    falhas_rede += 1
                    if falhas_rede == 3:
                        print("[Audio] Google Speech indisponivel; aguardando conexao.")
                    time.sleep(min(2.0, 0.25 * 2 ** min(falhas_rede, 3)))
                    continue
                falhas_rede = 0
                if chamada_exata(resultado.texto):
                    metricas.contar("ativacoes")
                    if ao_ativar is not None:
                        ao_ativar()
                    return "yasm " + remover_prefixo(resultado.texto)

        return recuperar_captura(aguardar_google)
    if _detector is None:
        preparar_reconhecimento()

    def aguardar():
        captura = obter_captura()
        voz.aguardar_microfone()
        captura.descartar()
        _detector.reset()
        anterior = deque(maxlen=150)  # 3 s, inclui nome + início do comando.
        while True:
            pcm = captura.ler()
            anterior.append(pcm)
            if _detector.alimentar(pcm):
                metricas.contar("ativacoes")
                if ao_ativar is not None:
                    ao_ativar()
                # Mesmo stream: não há fechamento/reabertura na transição.
                try:
                    audio = gravar_com_sounddevice(timeout=5.0, iniciais=tuple(anterior))
                except (sr.UnknownValueError, sr.WaitTimeoutError):
                    return "yasm"
                except FraseLonga:
                    return "yasm"
                resultado = transcrever_audio(audio)
                if resultado.texto:
                    return "yasm " + remover_prefixo(resultado.texto)
                return "yasm"
    return recuperar_captura(aguardar)


def _google(audio):
    recognizer = sr.Recognizer()
    recognizer.operation_timeout = TIMEOUT_INTERNET
    recognizer.dynamic_energy_threshold = False
    recognizer.energy_threshold = 80
    recognizer.pause_threshold = 0.45
    recognizer.phrase_threshold = 0.12
    recognizer.non_speaking_duration = 0.20
    return recognizer.recognize_google(audio, language=IDIOMA)


def _carregar_vosk():
    global _modelo_vosk
    global _aviso_modelo

    if _modelo_vosk is not None:
        return _modelo_vosk

    if Model is None:
        if not _aviso_modelo:
            print(
                "[Audio] O pacote Vosk nao esta instalado neste Python. "
                "Execute: python -m pip install -r requirements.txt"
            )
            _aviso_modelo = True
        return None

    if not MODELO_VOSK_DIR.is_dir():
        if not _aviso_modelo:
            print(
                "[Audio] Modelo Vosk offline nao encontrado em "
                f"{MODELO_VOSK_DIR}."
            )
            _aviso_modelo = True
        return None

    if SetLogLevel is not None:
        SetLogLevel(-1)

    try:
        _modelo_vosk = Model(str(MODELO_VOSK_DIR))
    except Exception as erro:
        if not _aviso_modelo:
            print(f"[Audio] Nao consegui carregar o modelo Vosk: {erro}")
            _aviso_modelo = True
        return None
    return _modelo_vosk


def motor_reconhecimento():
    reserva = f"; reserva {ASR_FALLBACK}" if ASR_FALLBACK != "nenhum" else ""
    return f"{ASR_MOTOR}{reserva}; ativacao {WAKE_MOTOR}"


def preparar_reconhecimento():
    global _detector, _preparado
    from ativacao_yasm import VoskAtivacao, PorcupineAtivacao
    if ASR_MOTOR not in {"google", "vosk", "groq", "faster-whisper"}:
        raise ValueError("YASM_ASR invalido")
    if ASR_FALLBACK not in {"nenhum", "vosk"}:
        raise ValueError("YASM_ASR_FALLBACK deve ser nenhum ou vosk")
    modelo = _carregar_vosk() if WAKE_MOTOR == "vosk" or ASR_MOTOR == "vosk" or ASR_FALLBACK == "vosk" else None
    if WAKE_MOTOR == "vosk":
        if modelo is None:
            raise RuntimeError("Ativacao local exige Vosk e modelo portugues")
        if _detector is None:
            _detector = VoskAtivacao(modelo, KaldiRecognizer)
            print("[Audio] Aliases no vocabulario: " + ", ".join(_detector.vocabulario))
    elif WAKE_MOTOR == "porcupine":
        if _detector is None:
            _detector = PorcupineAtivacao()
    elif WAKE_MOTOR == "google":
        pass
    else:
        raise ValueError("YASM_WAKE deve ser google, vosk ou porcupine")
    if ASR_MOTOR == "faster-whisper":
        _carregar_whisper()
    _vad_atual()
    _preparado = True
    return True


def _vosk(audio):
    modelo = _carregar_vosk()
    if modelo is None:
        raise sr.RequestError("Modelo Vosk indisponivel")
    reconhecedor = KaldiRecognizer(modelo, TAXA)
    reconhecedor.SetWords(False)
    reconhecedor.AcceptWaveform(audio.get_raw_data(convert_rate=TAXA, convert_width=2))
    return str(json.loads(reconhecedor.FinalResult()).get("text", "")).strip()


def _carregar_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        caminho = os.environ.get("YASM_FASTER_WHISPER_MODEL", "")
        if not caminho or not os.path.isdir(caminho):
            raise ValueError("Defina YASM_FASTER_WHISPER_MODEL como pasta de modelo local")
        _whisper = WhisperModel(caminho, device="cpu", compute_type="int8",
                                cpu_threads=min(4, os.cpu_count() or 1),
                                local_files_only=True)
    return _whisper


def _faster_whisper(audio):
    pcm = np.frombuffer(audio.get_raw_data(convert_rate=TAXA, convert_width=2), dtype="<i2")
    segmentos, _ = _carregar_whisper().transcribe(
        pcm.astype(np.float32) / 32768, language="pt", beam_size=3,
        condition_on_previous_text=False, vad_filter=False)
    return " ".join(s.text.strip() for s in segmentos
                    if s.no_speech_prob < 0.7 and s.avg_logprob > -1.2)


def transcrever_audio(audio, motor=None, *, usar_reserva=True):
    global ultimo_resultado
    identificador = next(_ids)
    motor = motor or (ASR_MOTOR if RECONHECIMENTO_ONLINE or ASR_MOTOR == "faster-whisper" else "vosk")
    if motor == "groq":
        import ia_yasm
        principal = ia_yasm.transcrever
    else:
        principal = {"google": _google, "vosk": _vosk,
                     "faster-whisper": _faster_whisper}[motor]
    inicio = time.monotonic()
    fallback = False
    status = "nao_entendi"
    texto = ""
    reserva = [("vosk", _vosk)] if usar_reserva and ASR_FALLBACK == "vosk" and motor != "vosk" else []
    for indice, (nome, funcao) in enumerate([(motor, principal)] + reserva):
        if indice:
            fallback = True
            metricas.contar("fallback_asr")
        try:
            texto = " ".join(str(funcao(audio) or "").split())
            if texto:
                status = "ok"
                motor = nome
                break
        except sr.UnknownValueError:
            status = "nao_entendi"
        except (TimeoutError, socket.timeout):
            status = "timeout"
            metricas.contar("timeout_asr")
        except Exception as erro:
            # Apenas tipo, nunca payload remoto, transcricao ou credencial.
            status = "servico_indisponivel"
            metricas.contar("falhas_asr")
            if DEBUG:
                print(f"[Audio] {nome}: {type(erro).__name__}")
    metricas.medir("transcricao", time.monotonic() - inicio)
    ultimo_resultado = ResultadoEscuta(identificador, texto, status, motor, fallback)
    if texto and LOG_TRANSCRICOES:
        print(f"Voce: {texto}")
    return ultimo_resultado


def escutar(timeout=None, frase_maxima=TEMPO_MAXIMO_FRASE, silencioso=True):
    global ultimo_resultado
    try:
        audio = recuperar_captura(lambda: gravar_com_sounddevice(timeout, frase_maxima))
        return transcrever_audio(audio).texto
    except sr.WaitTimeoutError:
        ultimo_resultado = ResultadoEscuta(status="silencio")
    except sr.UnknownValueError:
        ultimo_resultado = ResultadoEscuta(status="nao_entendi")
    except FraseLonga:
        ultimo_resultado = ResultadoEscuta(status="frase_longa")
    return ""
