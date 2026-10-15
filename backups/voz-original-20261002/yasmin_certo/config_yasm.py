from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
ARQUIVO_MEMORIA = BASE_DIR / "memoria.json"
IDIOMA = "pt-BR"

# Velocidade: limites curtos, sem sacrificar a captura sensivel.
TEMPO_MAXIMO_FRASE = 5.0
TEMPO_ESPERA_CONVERSA = 3.2
TEMPO_MODO_CONVERSA = 28.0
ATRASO_APOS_FALA = 0.25
TIMEOUT_INTERNET = 8
MAX_RESULTADOS_PESQUISA = 4
DEBUG = os.environ.get("YASM_DEBUG", "").lower() in ("1", "true", "sim")

# A maior parte da Yasm funciona localmente. Por escolha do usuario, o Google
# Speech e o reconhecedor principal; Vosk continua disponivel como reserva.
OFFLINE_PRIMEIRO = os.environ.get("YASM_OFFLINE_PRIMEIRO", "1").lower() not in (
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

# Configuracoes antigas de Groq mantidas apenas para compatibilidade do modulo
# ia_yasm.py. O fluxo principal nao carrega nem usa esse servico.
GROQ_WHISPER_MODEL = os.environ.get("YASM_WHISPER_MODEL", "whisper-large-v3")
GROQ_RESEARCH_MODEL = "groq/compound-mini"
GROQ_MAX_TOKENS = 1024
GROQ_TEMPERATURE = 0.10
GROQ_HISTORICO = 4

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
