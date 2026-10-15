"""Normalização e tokenização (usadas na indexação E na busca, para casarem)."""
import re
import unicodedata

STOP = set("""a o as os um uma uns umas de do da dos das em no na nos nas por para com sem e ou que se ao aos
é são foi ser como mais mas já não the an of to in on for and or is are was be it this that with at by from""".split())
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_TOK = re.compile(r"[a-z0-9]+")


def fold(s: str) -> str:
    """minúsculas e sem acentos."""
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def stem(t: str) -> str:
    return t[:-1] if len(t) > 4 and t.endswith("s") else t  # plural simples


def tokenize(text: str) -> list[str]:
    """camelCase/snake_case viram palavras separadas; stopwords saem."""
    out = []
    for t in _TOK.findall(fold(_CAMEL.sub(" ", text))):
        if len(t) < 2 or fold(t) in STOP:
            continue
        out.append(stem(t))
    return out
