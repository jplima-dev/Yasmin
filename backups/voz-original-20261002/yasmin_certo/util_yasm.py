import unicodedata
import re
from difflib import SequenceMatcher

VARIACOES_YASM = {
    "yasm", "yas", "yasmim", "yasmin", "yasmine", "yazmin", "yazmim",
    "yazminh", "iasm", "iasmin", "iasmim", "yasmim", "jasmin", "jasmine",
    "jasmim", "jasm", "yaz", "yasmi", "yasmim", "yasminh", "yasminha",
    "yazmine", "yasmine", "yasmyn", "yazmyn", "iasminha", "iasmine",
}

def normalizar(texto):
    texto = str(texto or "").lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^\w\s]", " ", texto, flags=re.UNICODE)
    return " ".join(texto.split())

def extrair_depois(texto, gatilhos):
    texto_normalizado = normalizar(texto)
    for gatilho in gatilhos:
        g = normalizar(gatilho)
        if not g:
            continue
        encontrado = re.search(r"(?<!\w)" + re.escape(g) + r"(?!\w)", texto_normalizado)
        if encontrado:
            return texto_normalizado[encontrado.end():].strip()
    return ""

def remover_palavras_iniciais(texto, palavras):
    partes = texto.split()
    while partes and partes[0] in palavras:
        partes.pop(0)
    return " ".join(partes).strip()

def palavra_parece_yasm(palavra):
    palavra = normalizar(palavra)
    if palavra in VARIACOES_YASM:
        return True
    # Muito tolerante para erros comuns do Whisper em nomes curtos.
    for alvo in ("yasm", "yasmin", "yasmim"):
        if SequenceMatcher(None, palavra, alvo).ratio() >= (0.72 if len(palavra) >= 4 else 0.80):
            return True
    return False

def remover_chamada(texto):
    palavras = normalizar(texto).split()
    while palavras and palavra_parece_yasm(palavras[0]):
        palavras.pop(0)
    return " ".join(palavras).strip()

def chamou_yasm(texto):
    return any(palavra_parece_yasm(p) for p in normalizar(texto).split())
