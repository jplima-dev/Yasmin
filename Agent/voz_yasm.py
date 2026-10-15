from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import socket
import subprocess
import tempfile
import threading
import time
import wave
import uuid
from concurrent.futures import ThreadPoolExecutor
from pipeline_voz import metricas
from pathlib import Path

try:
    import winsound
except ImportError:
    winsound = None

from config_yasm import ATRASO_APOS_FALA, VOZ_YASM, CACHE_VOZ, LOG_TRANSCRICOES, DEBUG
from memoria_yasm import memoria


_ultima_fala = 0.0
_voz_temporaria = None
_CACHE_DIR = Path(__file__).resolve().parent / ".voz_cache"
_MODELO_KITSUNE = Path(__file__).resolve().parent / "models" / "kitsune-tts" / "kitsune39M.onnx"
_CONFIG_KITSUNE = Path(__file__).resolve().parent / "models" / "kitsune-tts" / "model_config.json"
_AMOSTRAS_VOZ = Path(__file__).resolve().parent / "amostras_voz"
_sintetizador_kitsune = None
_kitsune_lock = threading.RLock()
_aquecimento_lock = threading.Lock()
_aquecimento_iniciado = False
_fala_lock = threading.RLock()
_falando = threading.Event()
_reproduzindo = threading.Event()
_fim_reproducao = 0.0
_HOST_VOZ = "127.0.0.1"
_PORTA_VOZ = 45455

_VOZES_ANTIGAS = {
    "pt-br-franciscaneural": "kitsune:emilia",
    "pt-br-antonioneural": "kitsune:frieren",
    "pt-br-thalitamultilingualneural": "kitsune:violet",
}


def vozes_com_amostra() -> tuple[str, ...]:
    """Vozes presentes na pasta de amostras e no modelo de sintese."""
    try:
        speakers = json.loads(_CONFIG_KITSUNE.read_text(encoding="utf-8"))["speakers"]
        if not isinstance(speakers, dict):
            return ()
        return tuple(
            f"kitsune:{arquivo.stem}"
            for arquivo in sorted(_AMOSTRAS_VOZ.glob("*.wav"))
            if (arquivo.stem in speakers and arquivo.is_file()
                and arquivo.resolve().is_relative_to(_AMOSTRAS_VOZ.resolve()))
        )
    except (OSError, ValueError, KeyError, TypeError):
        return ()


def _arquivo_amostra(voz_id: str) -> Path | None:
    voz_id = _VOZES_ANTIGAS.get(str(voz_id).casefold(), str(voz_id))
    if voz_id not in vozes_com_amostra():
        return None
    return _AMOSTRAS_VOZ / f"{voz_id.partition(':')[2]}.wav"


def reproduzir_amostra(voz_id: str) -> bool:
    """Toca a amostra original na escolha da voz, sem alterar o arquivo fonte."""
    global _ultima_fala, _fim_reproducao
    origem = _arquivo_amostra(voz_id)
    if origem is None or winsound is None:
        return False
    try:
        import numpy as np
        from scipy.io.wavfile import read, write

        taxa, audio = read(origem)
        if taxa <= 0 or np.asarray(audio).size == 0:
            return False
        audio = np.asarray(audio)
        if audio.dtype == np.int16:
            reproduzir = origem
            temporario = None
        else:
            if np.issubdtype(audio.dtype, np.floating):
                pcm = np.clip(np.nan_to_num(audio), -1.0, 1.0)
                pcm = (pcm * 32767).astype(np.int16)
            elif np.issubdtype(audio.dtype, np.integer):
                limites = np.iinfo(audio.dtype)
                centro = (limites.max + 1) / 2 if limites.min == 0 else 0
                escala = centro or max(abs(limites.min), limites.max)
                pcm = np.clip((audio.astype(np.float64) - centro) / escala * 32767,
                              -32768, 32767).astype(np.int16)
            else:
                return False
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as arquivo:
                temporario = Path(arquivo.name)
            write(str(temporario), taxa, pcm)
            reproduzir = temporario
        try:
            if not _wav_valido(reproduzir):
                return False
            with _fala_lock:
                _falando.set()
                _reproduzindo.set()
                try:
                    winsound.PlaySound(str(reproduzir), winsound.SND_FILENAME | winsound.SND_NODEFAULT)
                    _fim_reproducao = time.monotonic()
                finally:
                    _ultima_fala = time.monotonic()
                    _reproduzindo.clear()
                    _falando.clear()
            return True
        finally:
            if temporario is not None:
                temporario.unlink(missing_ok=True)
    except (OSError, ValueError, TypeError, RuntimeError):
        return False


def obter_voz_atual() -> str:
    if _voz_temporaria:
        return _VOZES_ANTIGAS.get(_voz_temporaria.casefold(), _voz_temporaria)

    try:
        voz_salva = memoria.get("voz", {}).get("id")
        if voz_salva:
            voz_salva = str(voz_salva).strip()
            return _VOZES_ANTIGAS.get(voz_salva.casefold(), voz_salva)
    except Exception:
        pass

    return _VOZES_ANTIGAS.get(VOZ_YASM.casefold(), VOZ_YASM)


def definir_voz_temporaria(voz_id: str | None) -> None:
    global _voz_temporaria
    voz_id = str(voz_id or "").strip()
    _voz_temporaria = voz_id or None


def limpar_voz_temporaria() -> None:
    global _voz_temporaria
    _voz_temporaria = None


def definir_voz(voz_id: str) -> None:
    global _voz_temporaria
    voz_id = str(voz_id or "").strip()
    if not voz_id:
        return

    _voz_temporaria = voz_id
    try:
        memoria.setdefault("voz", {})["id"] = voz_id
    except Exception:
        pass


def _voz_windows() -> str:
    """Converte os IDs antigos do Edge para vozes locais do Windows."""
    voz = obter_voz_atual().casefold()
    if "antonio" in voz or "daniel" in voz:
        return "Microsoft Daniel"
    return "Microsoft Maria"


def _arquivo_cache(texto: str) -> Path:
    if not CACHE_VOZ:
        return _CACHE_DIR / f"sessao-{uuid.uuid4().hex}.wav"
    chave = hashlib.sha1(
        f"offline-v3\n{obter_voz_atual()}\n{texto}".encode("utf-8")
    ).hexdigest()
    return _CACHE_DIR / f"{chave}.wav"


def _wav_valido(arquivo: Path) -> bool:
    """Ignora arquivos incompletos deixados por uma sintese interrompida."""
    try:
        with wave.open(str(arquivo), "rb") as wav:
            tamanho = wav.getnframes() * wav.getnchannels() * wav.getsampwidth()
            if tamanho <= 0 or tamanho > arquivo.stat().st_size:
                return False
            return len(wav.readframes(wav.getnframes())) == tamanho
    except (OSError, EOFError, wave.Error):
        return False


def _carregar_kitsune():
    # O aquecimento e a primeira fala podem ocorrer em threads diferentes.
    with _kitsune_lock:
        return _inicializar_kitsune()


def _inicializar_kitsune():
    global _sintetizador_kitsune

    if _sintetizador_kitsune is not None:
        return _sintetizador_kitsune

    if not _MODELO_KITSUNE.is_file() or not _CONFIG_KITSUNE.is_file():
        raise RuntimeError("Modelo de voz Kitsune nao encontrado.")

    import espeakng_loader

    os.environ.setdefault(
        "PHONEMIZER_ESPEAK_LIBRARY",
        str(espeakng_loader.get_library_path()),
    )
    os.environ.setdefault(
        "ESPEAK_DATA_PATH",
        str(espeakng_loader.get_data_path()),
    )

    from kitsune.api import KitsuneSynthesizer

    _sintetizador_kitsune = KitsuneSynthesizer(
        onnx_path=str(_MODELO_KITSUNE),
        config=str(_CONFIG_KITSUNE),
        ort_threads=max(1, min(8, os.cpu_count() or 2)),
    )
    return _sintetizador_kitsune


def _gerar_wav_kitsune(texto: str, arquivo: Path, voz_id: str) -> bool:
    import numpy as np
    from scipy.io.wavfile import write

    speaker = voz_id.partition(":")[2] or "emilia"

    with _kitsune_lock:
        sintetizador = _carregar_kitsune()
        audio = sintetizador.synthesize(
            texto,
            speaker=speaker,
            lang="pt-br",
            noise_scale=0.62,
            length_scale=0.94,
        )
        audio = np.asarray(audio)
        if not np.issubdtype(audio.dtype, np.integer):
            audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
            audio = np.clip(audio * 32768.0, -32768, 32767).astype(np.int16)
        elif audio.dtype != np.int16:
            audio = np.clip(audio, -32768, 32767).astype(np.int16)

        # PCM int16 e reproduzivel pelo PlaySound do Windows; o WAV float
        # produzido diretamente pelo scipy nao e aceito por todos os drivers.
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=arquivo.parent, suffix=".wav", delete=False) as tmp:
            temporario = Path(tmp.name)
        try:
            write(str(temporario), sintetizador.sample_rate, audio)
            if not _wav_valido(temporario):
                return False
            temporario.replace(arquivo)
        finally:
            temporario.unlink(missing_ok=True)

    return _wav_valido(arquivo)


def _gerar_via_servico(texto: str, arquivo: Path, voz_id: str) -> bool:
    mensagem = json.dumps(
        {"texto": texto, "arquivo": str(arquivo), "voz": voz_id},
        ensure_ascii=False,
    ).encode("utf-8") + b"\n"

    try:
        with socket.create_connection((_HOST_VOZ, _PORTA_VOZ), timeout=0.35) as cliente:
            cliente.settimeout(45.0)
            cliente.sendall(mensagem)
            resposta = b""
            while b"\n" not in resposta and len(resposta) < 65536:
                parte = cliente.recv(4096)
                if not parte:
                    break
                resposta += parte

        dados = json.loads(resposta.split(b"\n", 1)[0].decode("utf-8"))
        return isinstance(dados, dict) and dados.get("ok") is True and _wav_valido(arquivo)
    except (OSError, ValueError):
        return False


def _gerar_wav_offline(texto: str, arquivo: Path) -> bool:
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    voz_id = obter_voz_atual()

    if voz_id.startswith("kitsune:"):
        if _gerar_via_servico(texto, arquivo, voz_id):
            return True

        try:
            if _gerar_wav_kitsune(texto, arquivo, voz_id):
                return True
        except Exception as erro:
            print(
                "[Voz neural local] Usando Maria como reserva: "
                f"{type(erro).__name__}: {erro!r}"
            )

    with tempfile.NamedTemporaryFile(dir=arquivo.parent, suffix=".wav", delete=False) as tmp:
        temporario = Path(tmp.name)

    texto_b64 = base64.b64encode(texto.encode("utf-8")).decode("ascii")
    caminho_b64 = base64.b64encode(str(temporario).encode("utf-8")).decode("ascii")
    voz_b64 = base64.b64encode(_voz_windows().encode("utf-8")).decode("ascii")

    script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$texto = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{texto_b64}'))
$arquivo = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{caminho_b64}'))
$voz = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{voz_b64}'))
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{ $s.SelectVoice($voz) }} catch {{ }}
$s.Rate = 1
$s.Volume = 100
try {{
    $s.SetOutputToWaveFile($arquivo)
    $s.Speak($texto)
}} finally {{ $s.Dispose() }}
"""
    comando = base64.b64encode(script.encode("utf-16le")).decode("ascii")

    try:
        resultado = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", comando],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=45,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        if resultado.returncode == 0 and _wav_valido(temporario):
            temporario.replace(arquivo)
            return True
        return False
    except Exception as erro:
        print(f"[Voz offline] {type(erro).__name__}: {erro!r}")
        return False
    finally:
        temporario.unlink(missing_ok=True)


def preparar_voz() -> bool:
    """Mantido por compatibilidade com a interface de configuracao."""
    return True


def _dividir_texto(texto: str, limite: int = 420) -> list[str]:
    import textwrap

    if limite <= 0:
        raise ValueError("O limite de texto deve ser positivo.")
    if len(texto) <= limite:
        return [texto]

    partes = [
        trecho
        for frase in re.split(r"(?<=[.!?])\s+", texto)
        for trecho in textwrap.wrap(frase, width=limite, break_on_hyphens=False)
    ]
    blocos = []
    atual = ""

    for parte in partes:
        candidato = f"{atual} {parte}".strip()
        if atual and len(candidato) > limite:
            blocos.append(atual)
            atual = parte
        else:
            atual = candidato

    if atual:
        blocos.append(atual)

    return blocos


def _blocos_resposta_rapida(texto: str) -> list[str]:
    """Primeiro trecho curto reduz o tempo ate a primeira palavra reproduzida."""
    if len(texto) <= 72:
        return [texto]
    candidatos = [m.end() for m in re.finditer(r"[,;.!?](?:\s|$)", texto[:90])
                  if 24 <= m.end() <= 80]
    if not candidatos and len(texto.split()[0]) <= 80:
        # Sem fim natural de oração, preservar a frase curta inteira evita
        # uma pausa artificial ou mudança de entonação no meio da ideia.
        return _dividir_texto(texto, limite=220)
    corte = candidatos[0] if candidatos else texto.rfind(" ", 24, 73)
    if corte < 24:
        corte = texto.find(" ", 72)
    if corte < 0 or corte > 80:
        corte = 72
    return [texto[:corte].strip()] + _dividir_texto(texto[corte:].strip(), limite=220)


def _preparar_bloco(bloco: str):
    arquivo = _arquivo_cache(bloco)
    existia = arquivo.exists()
    inicio = time.monotonic()
    pronto = _wav_valido(arquivo) or _gerar_wav_offline(bloco, arquivo)
    return arquivo, existia, pronto, time.monotonic() - inicio


def falar(texto) -> bool:
    with _fala_lock:
        _falando.set()
        try:
            return _falar_serializado(texto)
        finally:
            _falando.clear()


def microfone_bloqueado():
    return _falando.is_set() or segundos_desde_fala() < ATRASO_APOS_FALA


def falando() -> bool:
    """Playback real com uma curta janela para a atualização visual."""
    return _reproduzindo.is_set() or time.monotonic() - _fim_reproducao < 0.7


def _falar_serializado(texto) -> bool:
    global _ultima_fala, _fim_reproducao
    texto = " ".join(str(texto or "").split()).strip()
    if not texto:
        return False
    if LOG_TRANSCRICOES:
        print(f"Yasm: {texto}")
    futuros = []
    try:
        if winsound is None:
            return False
        blocos = _blocos_resposta_rapida(texto)
        primeira = True
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="yasm-sintese") as pool:
            atual = pool.submit(_preparar_bloco, blocos[0])
            futuros.append(atual)
            for indice, _ in enumerate(blocos):
                arquivo, _, pronto, duracao = atual.result()
                if not pronto:
                    return False
                metricas.medir("sintese", duracao)
                proximo = None
                if indice + 1 < len(blocos):
                    proximo = pool.submit(_preparar_bloco, blocos[indice + 1])
                    futuros.append(proximo)
                if primeira and metricas.fim_fala is not None:
                    latencia = time.monotonic() - metricas.fim_fala
                    metricas.medir("fim_fala_ate_reproducao", latencia)
                    if latencia > 2.0:
                        metricas.contar("respostas_acima_2s")
                    if DEBUG:
                        print(f"[LATENCIA] fim da fala ate inicio da resposta: {latencia:.2f}s")
                    metricas.fim_fala = None
                primeira = False
                inicio = time.monotonic()
                _reproduzindo.set()
                try:
                    winsound.PlaySound(str(arquivo), winsound.SND_FILENAME | winsound.SND_NODEFAULT)
                    _fim_reproducao = time.monotonic()
                finally:
                    _reproduzindo.clear()
                metricas.medir("reproducao", time.monotonic() - inicio)
                atual = proximo
        return True
    except Exception as erro:
        print(f"[Voz offline] {type(erro).__name__}")
        return False
    finally:
        if not CACHE_VOZ:
            for futuro in futuros:
                if futuro.done() and not futuro.cancelled():
                    try:
                        arquivo, existia, _, _ = futuro.result()
                        if not existia:
                            arquivo.unlink(missing_ok=True)
                    except Exception:
                        pass
        _ultima_fala = time.monotonic()


def segundos_desde_fala() -> float:
    return time.monotonic() - _ultima_fala


def aguardar_microfone() -> None:
    with _fala_lock:
        restante = ATRASO_APOS_FALA - segundos_desde_fala()
        if restante > 0:
            time.sleep(restante)


def _aquecer_motor_local() -> None:
    """Prepara o modelo ao iniciar yas.py diretamente, sem o launcher."""
    time.sleep(0.25)
    try:
        with socket.create_connection((_HOST_VOZ, _PORTA_VOZ), timeout=0.25):
            return
    except OSError:
        pass

    try:
        _carregar_kitsune()
    except Exception:
        pass


def aquecer_motor_em_segundo_plano() -> None:
    """Aquece a voz ao iniciar o programa, sem carregar o modelo em importações de texto."""
    global _aquecimento_iniciado
    if os.environ.get("YASM_VOICE_SERVER") == "1":
        return
    with _aquecimento_lock:
        if _aquecimento_iniciado:
            return
        _aquecimento_iniciado = True
        threading.Thread(target=_aquecer_motor_local, daemon=True,
                         name="yasm-voice-warmup").start()
