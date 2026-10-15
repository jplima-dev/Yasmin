from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_MEMORIA = BASE_DIR / "memoria.json"
IDIOMA = "pt-BR"

# Velocidade: limites curtos, sem sacrificar a captura sensivel.
TEMPO_MAXIMO_FRASE = 20.0
TEMPO_ESPERA_CONVERSA = 3.2
TEMPO_MODO_CONVERSA = 28.0
ATRASO_APOS_FALA = 0.10
TIMEOUT_INTERNET = 8
MAX_RESULTADOS_PESQUISA = 4
DEBUG = os.environ.get("YASM_DEBUG", "").lower() in ("1", "true", "sim")

# O microfone e capturado localmente; Google Speech reconhece a fala por padrao.
# Vosk so e usado quando configurado explicitamente ou no modo offline.
OFFLINE_PRIMEIRO = os.environ.get("YASM_OFFLINE_PRIMEIRO", "0").lower() not in (
    "0", "false", "nao", "off",
)
RECONHECIMENTO_ONLINE = os.environ.get(
    "YASM_RECONHECIMENTO_ONLINE", "1"
).lower() in ("1", "true", "sim", "yes", "on")
MODELO_VOSK_DIR = Path(
    os.environ.get(
        "YASM_VOSK_MODEL",
        str(BASE_DIR / "models" / "vosk-model-small-pt-0.3"),
    )
)

# Groq permanece opcional; comandos conhecidos são executados localmente.
GROQ_WHISPER_MODEL = os.environ.get("YASM_WHISPER_MODEL", "whisper-large-v3")
GROQ_RESEARCH_MODEL = "groq/compound-mini"
GROQ_MAX_TOKENS = 1024
GROQ_TEMPERATURE = 0.10
GROQ_HISTORICO = 4


def opcao_bool(nome, padrao=False):
    return os.environ.get(nome, "1" if padrao else "0").lower() in ("1", "true", "sim", "on")


def opcao_numero(nome, padrao, minimo, maximo):
    valor = float(os.environ.get(nome, padrao))
    if not minimo <= valor <= maximo:
        raise ValueError(f"{nome} deve estar entre {minimo} e {maximo}")
    return valor


ASR_MOTOR = os.environ.get("YASM_ASR", "google" if RECONHECIMENTO_ONLINE else "vosk").lower()
WAKE_MOTOR = os.environ.get("YASM_WAKE", "google" if RECONHECIMENTO_ONLINE else "vosk").lower()
ASR_FALLBACK = os.environ.get("YASM_ASR_FALLBACK", "nenhum").lower()
VAD_MOTOR = os.environ.get("YASM_VAD", "auto").lower()
SILENCIO_COMANDO = opcao_numero("YASM_SILENCIO_FIM", 0.65, 0.3, 2.0)
SILENCIO_CURTO = opcao_numero("YASM_SILENCIO_CURTO", min(0.40, SILENCIO_COMANDO), 0.3, SILENCIO_COMANDO)
LOG_TRANSCRICOES = opcao_bool("YASM_LOG_TRANSCRICOES")
PERSISTIR_HISTORICO = opcao_bool("YASM_PERSISTIR_HISTORICO")
CACHE_VOZ = opcao_bool("YASM_CACHE_VOZ")
REDUZIR_RUIDO = opcao_bool("YASM_REDUZIR_RUIDO")
AUTO_GAIN = opcao_bool("YASM_AUTO_GAIN", True)

VOZ_YASM = "pt-BR-FranciscaNeural"

SITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "youtube music": "https://music.youtube.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "whatsapp": "https://web.whatsapp.com",
    "whatsapp web": "https://web.whatsapp.com",
    "spotify": "https://open.spotify.com",
    "documentacao python": "https://docs.python.org/pt-br/3/",
    "python docs": "https://docs.python.org/pt-br/3/",
    "pypi": "https://pypi.org",
    "stack overflow": "https://stackoverflow.com/questions/tagged/python",
}
