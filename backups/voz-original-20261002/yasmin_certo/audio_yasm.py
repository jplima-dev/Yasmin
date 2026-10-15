import json
import os
import time
from collections import deque

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
#   microfone -> VAD por energia + faixa vocal -> anti-ruido
#   -> ganho automatico -> Vosk local
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

AGC_TARGET_RMS = 0.095
AGC_MAX = 9.0

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
    except Exception:
        return None

    for indice, dispositivo in enumerate(dispositivos):
        nome = str(dispositivo.get("name", ""))
        canais = int(dispositivo.get("max_input_channels", 0) or 0)

        if canais > 0 and escolha_n in nome.casefold():
            return indice

    print(f"[Audio] Nao encontrei microfone com nome contendo: {escolha}")
    return None


def diagnostico_audio():
    try:
        dispositivo = _dispositivo_entrada()
        if dispositivo is None:
            padrao = sd.query_devices(kind="input")
            return f"microfone padrao: {padrao.get('name', 'desconhecido')}"

        escolhido = sd.query_devices(dispositivo)
        return f"microfone selecionado: {escolhido.get('name', dispositivo)}"
    except Exception as erro:
        return f"diagnostico indisponivel: {type(erro).__name__}"


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

    print("Yasm: Calibrando meu microfone. Fique em silencio por dois segundos.")

    dados = sd.rec(
        int(TAXA * duracao),
        samplerate=TAXA,
        channels=CANAL,
        dtype="float32",
        device=_dispositivo_entrada(),
    )
    sd.wait()

    samples = _audio_float(dados)

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
        ganho = min(AGC_MAX, AGC_TARGET_RMS / rms)
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


def gravar_com_sounddevice(timeout=None, frase_maxima=TEMPO_MAXIMO_FRASE):
    """Captura uma frase com VAD e anti-ruido."""

    voz.aguardar_microfone()

    inicio_espera = time.monotonic()
    prebuffer = deque(maxlen=PREBUFFER_BLOCOS)
    blocos = []
    inicio_fala = None
    ultima_voz = None
    blocos_inicio = 0
    blocos_ruido = 0

    try:
        with sd.InputStream(
            samplerate=TAXA,
            channels=CANAL,
            dtype="int16",
            blocksize=BLOCO,
            device=_dispositivo_entrada(),
        ) as stream:
            while True:
                dados, status = stream.read(BLOCO)
                agora = time.monotonic()

                if status and DEBUG:
                    print(f"[Audio] status={status}")

                bloco = dados[:, 0].copy()
                energia = _rms(bloco)

                if inicio_fala is None:
                    prebuffer.append(bloco)

                    if _parece_fala(
                        bloco,
                        energia,
                        global_start_threshold,
                        iniciando=True,
                    ):
                        blocos_inicio += 1
                    else:
                        blocos_inicio = max(0, blocos_inicio - 1)

                    if blocos_inicio >= INICIO_BLOCOS:
                        inicio_fala = agora - (INICIO_BLOCOS * BLOCO_MS / 1000.0)
                        ultima_voz = agora
                        blocos.extend(list(prebuffer))
                        continue

                    if timeout is not None and agora - inicio_espera >= timeout:
                        raise sr.WaitTimeoutError()

                    continue

                blocos.append(bloco)

                if _parece_fala(
                    bloco,
                    energia,
                    global_continue_threshold,
                    iniciando=False,
                ):
                    ultima_voz = agora
                    blocos_ruido = 0
                else:
                    blocos_ruido += 1

                if ultima_voz is not None and agora - ultima_voz >= SILENCIO_FIM:
                    break

                if agora - inicio_fala >= frase_maxima:
                    break

                # Ruido continuo que passou pelo inicio nao deve prender a Yasm.
                if blocos_ruido * BLOCO_MS / 1000.0 > max(1.2, SILENCIO_FIM * 2):
                    break

    except sd.PortAudioError as erro:
        raise OSError(str(erro)) from erro

    if not blocos:
        raise sr.UnknownValueError()

    audio_int16 = _normalizar_audio(blocos)
    duracao = len(audio_int16) / TAXA

    if duracao < MIN_DURACAO_AUDIO:
        raise sr.UnknownValueError()

    audio_limpo = _remover_ruido(audio_int16)
    rms_total = _rms(audio_limpo)

    if rms_total < max(6.0, global_noise_rms * 0.30):
        raise sr.UnknownValueError()

    return sr.AudioData(audio_limpo.tobytes(), TAXA, 2)


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
    if RECONHECIMENTO_ONLINE:
        if Model is not None and MODELO_VOSK_DIR.is_dir():
            return "Google Speech (Vosk como reserva)"
        return "Google Speech"
    if Model is not None and MODELO_VOSK_DIR.is_dir():
        return "Vosk local (pt-BR)"
    return "offline aguardando modelo Vosk"


def preparar_reconhecimento():
    if RECONHECIMENTO_ONLINE:
        return True
    return _carregar_vosk() is not None


def _vosk(audio):
    modelo = _carregar_vosk()
    if modelo is None:
        raise sr.UnknownValueError()

    reconhecedor = KaldiRecognizer(modelo, TAXA)
    reconhecedor.SetWords(False)
    reconhecedor.AcceptWaveform(
        audio.get_raw_data(convert_rate=TAXA, convert_width=2)
    )
    resultado = json.loads(reconhecedor.FinalResult())
    return str(resultado.get("text", "")).strip()


def escutar(timeout=None, frase_maxima=TEMPO_MAXIMO_FRASE, silencioso=True):
    """Usa Google Speech como principal e Vosk como reserva local."""

    while True:
        try:
            audio = gravar_com_sounddevice(timeout, frase_maxima)
            if RECONHECIMENTO_ONLINE:
                try:
                    texto = _google(audio).strip()
                except sr.RequestError as erro:
                    print(
                        "[Audio] Google indisponivel; usando Vosk local: "
                        f"{type(erro).__name__}"
                    )
                    texto = _vosk(audio).strip()
                except sr.UnknownValueError:
                    texto = _vosk(audio).strip()
            else:
                texto = _vosk(audio).strip()

            if not texto:
                return ""

            texto = " ".join(texto.split())
            limpo = "".join(
                c for c in texto
                if c.isalnum() or c.isspace()
            ).strip()

            if not limpo:
                return ""

            print(f"Voce: {texto}")
            return texto

        except sr.WaitTimeoutError:
            return ""

        except sr.UnknownValueError:
            if not silencioso and DEBUG:
                print("[Audio] fala nao reconhecida")
            return ""

        except sr.RequestError as erro:
            print(f"[Audio online opcional] {type(erro).__name__}: {erro!r}")
            return ""

        except Exception as erro:
            print(f"[Erro audio] {type(erro).__name__}: {erro!r}")

            if DEBUG:
                import traceback
                traceback.print_exc()

            return ""
