import io
import wave
import os
import re
from config_yasm import GROQ_WHISPER_MODEL, GROQ_RESEARCH_MODEL, GROQ_MAX_TOKENS, GROQ_TEMPERATURE, GROQ_HISTORICO
from memoria_yasm import memoria

try:
    from groq import Groq
except ImportError:
    Groq = None

cliente = None
if Groq is not None and os.environ.get("GROQ_API_KEY"):
    try:
        cliente = Groq(api_key=os.environ["GROQ_API_KEY"])
    except Exception as erro:
        print(f"[Aviso] Groq indisponivel: {type(erro).__name__}: {erro!r}")


def disponivel():
    return cliente is not None


def _wav(audio):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(audio.sample_width)
        wav_file.setframerate(audio.sample_rate)
        wav_file.writeframes(audio.frame_data)
    return buffer.getvalue()


_ULTIMA_TRANSCRICAO = ""

def _texto_do_resultado(resultado):
    texto = (getattr(resultado, "text", None) or "").strip()
    segmentos = getattr(resultado, "segments", None) or []

    # Whisper fornece no_speech_prob em verbose_json. Se todos os segmentos
    # indicarem alta probabilidade de silencio, descartamos a transcricao.
    if segmentos:
        probabilidades = []
        for segmento in segmentos:
            valor = getattr(segmento, "no_speech_prob", None)
            if valor is None and isinstance(segmento, dict):
                valor = segmento.get("no_speech_prob")
            if valor is not None:
                try:
                    probabilidades.append(float(valor))
                except (TypeError, ValueError):
                    pass
        if probabilidades and max(probabilidades) >= 0.86 and sum(probabilidades) / len(probabilidades) >= 0.70:
            return ""

    # Descarta segmentos com confianca muito baixa. Isso reduz alucinacoes
    # em silencio e ruido, especialmente frases curtissimas.
    logprobs = []
    for segmento in segmentos:
        valor = getattr(segmento, "avg_logprob", None)
        if valor is None and isinstance(segmento, dict):
            valor = segmento.get("avg_logprob")
        if valor is not None:
            try:
                logprobs.append(float(valor))
            except (TypeError, ValueError):
                pass
    if logprobs and max(logprobs) < -1.15:
        return ""

    return texto

def transcrever(audio):
    global _ULTIMA_TRANSCRICAO

    if cliente is None:
        raise RuntimeError("Groq nao configurado.")

    dados = _wav(audio)
    resultado = cliente.audio.transcriptions.create(
        file=("yasm.wav", dados),
        model=GROQ_WHISPER_MODEL,
        language="pt",
        prompt=(
            "Assistente de voz chamada Yasm. Contexto de voz em portugues do Brasil. "
            "Nomes importantes: Yasm, Yas, Yasmin, Yasmim, Yasmine. "
            "Comandos comuns: tchau, ate logo, encerrar, desligar. "
            "Transcreva somente o que estiver realmente falado no audio. Se houver duvida ou silencio, retorne uma transcricao vazia. Nao invente frases curtas como 'e ai', 'obrigado' ou pontuacao quando nao estiverem claramente no audio."
        ),
        response_format="verbose_json",
        temperature=0.0,
    )

    texto = _texto_do_resultado(resultado)
    return texto

def limpar_transcricao(texto):
    global _ULTIMA_TRANSCRICAO

    texto = re.sub(r"\s+", " ", str(texto or "")).strip()
    texto_sem_pontuacao = re.sub(r"[\W_]+", " ", texto, flags=re.UNICODE).strip()
    if not texto_sem_pontuacao:
        return ""

    # Frases curtissimas muito comuns em alucinacoes de silencio.
    if texto_sem_pontuacao.casefold() in {".", "e ai", "obrigado", "obrigada"} and len(texto_sem_pontuacao.split()) <= 2:
        return ""

    # Nao deixa a mesma alucinacao aparecer repetidamente sem nova fala real.
    chave = texto.casefold()
    if chave == _ULTIMA_TRANSCRICAO:
        _ULTIMA_TRANSCRICAO = ""
        return ""

    _ULTIMA_TRANSCRICAO = chave
    return texto


def eh_pesquisa(texto):
    t = texto.lower().strip()
    gatilhos = (
        "quem ", "qual ", "quais ", "quando ", "onde ", "quantos ", "quantas ",
        "quanto ", "por que ", "porque ", "como foi ", "quem ganhou", "quem venceu",
        "qual foi", "qual era", "o que aconteceu", "pesquise", "pesquisa", "procure",
        "me diga sobre", "me fale sobre", "noticia", "notícias", "hoje", "atualmente",
        "agora", "ultimo", "último", "ultimos", "últimos", "recente", "mundial",
        "copa de", "copa do mundo", "brasileirao", "brasileirão",
    )
    return any(x in t for x in gatilhos)


def pesquisar(texto):
    if cliente is None:
        return None

    texto = str(texto).strip()

    if not texto:
        return None

    # Limite de segurança para a consulta.
    texto = texto[:1000]

    mensagens = [
        {
            "role": "system",
            "content": (
                "Voce e a Yasm, uma assistente brasileira. "
                "Responda em portugues do Brasil. "
                "Esta e uma pesquisa. "
                "Seja objetiva, clara e curta. "
                "Nao invente informacoes. "
                "Use somente os dados fornecidos na consulta."
            ),
        },
        {
            "role": "user",
            "content": texto,
        },
    ]

    try:
        resposta = cliente.chat.completions.create(
            model=GROQ_RESEARCH_MODEL,
            messages=mensagens,
            max_tokens=GROQ_MAX_TOKENS,
            temperature=0.2,
        )

        conteudo = resposta.choices[0].message.content

        if not conteudo:
            return None

        return conteudo.strip()

    except Exception as erro:
        print(
            f"[Erro pesquisa Groq] "
            f"{type(erro).__name__}: {erro!r}"
        )
        return None