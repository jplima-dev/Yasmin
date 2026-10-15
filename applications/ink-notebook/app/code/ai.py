"""Camada de IA (opcional). Nada é enviado sem provedor configurado; provedores externos pedem revisão do contexto."""
import json
import urllib.error
import urllib.request
from typing import Protocol
from urllib.parse import urlparse

from .. import db

DEFAULTS = {"ai_provider": "none", "ai_base_url": "", "ai_model": "", "ai_key": "",
            "ctx_max_chars": "12000", "review_external": "1"}
LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}


class AIProvider(Protocol):
    name: str
    external: bool

    def generate(self, system: str, prompt: str) -> str: ...


class AIError(Exception):
    pass


def _post(url, body, headers, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",**headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise AIError(f"o provedor respondeu {e.code}: {e.read().decode('utf-8', 'ignore')[:200]}")
    except Exception as e:
        raise AIError(f"não consegui falar com o provedor ({e})")


def _is_external(url):
    return (urlparse(url).hostname or "") not in LOOPBACK


class OllamaProvider:
    def __init__(self, base, model):
        self.base = (base or "http://127.0.0.1:11434").rstrip("/")
        self.model, self.name, self.external = model or "llama3.1", f"Ollama ({model or 'llama3.1'})", _is_external(self.base)

    def generate(self, system, prompt):
        d = _post(f"{self.base}/api/chat", {"model": self.model, "stream": False,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}, {})
        return d["message"]["content"]


class OpenAICompatProvider:
    """OpenAI e qualquer servidor compatível (LM Studio, vLLM, OpenRouter...)."""
    def __init__(self, base, model, key):
        self.base = (base or "https://api.openai.com/v1").rstrip("/")
        self.model, self.key = model or "gpt-4o-mini", key
        self.name, self.external = f"OpenAI-compatível ({self.model})", _is_external(self.base)

    def generate(self, system, prompt):
        h = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        d = _post(f"{self.base}/chat/completions", {"model": self.model, "temperature": 0.2,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}, h)
        return d["choices"][0]["message"]["content"]


class GeminiProvider:
    external = True

    def __init__(self, model, key):
        self.model, self.key = model or "gemini-2.0-flash", key
        self.name = f"Gemini ({self.model})"

    def generate(self, system, prompt):
        d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                  {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": prompt}]}]},
                  {"x-goog-api-key": self.key})
        return d["candidates"][0]["content"]["parts"][0]["text"]


def load_settings(conn):
    s = dict(DEFAULTS)
    s.update({r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM code_settings")})
    return s


def save_settings(conn, data: dict):
    for k, v in data.items():
        if k in DEFAULTS and not (k == "ai_key" and v in (None, "")):  # chave vazia = manter a atual
            conn.execute("INSERT INTO code_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))


def public_settings(s):
    return {**s, "ai_key": "", "has_key": bool(s["ai_key"])}


def get_provider(s):
    p = s["ai_provider"]
    if p == "ollama":
        return OllamaProvider(s["ai_base_url"], s["ai_model"])
    if p == "openai":
        return OpenAICompatProvider(s["ai_base_url"], s["ai_model"], s["ai_key"])
    if p == "gemini" and s["ai_key"]:
        return GeminiProvider(s["ai_model"], s["ai_key"])
    return None


SYSTEM = ("Você é um assistente que explica um projeto de software usando SOMENTE o contexto fornecido (extraído de um índice local). "
          "Responda em português do Brasil, de forma natural e didática, explicando o fluxo e o motivo, não só listando arquivos. "
          "Cite arquivos e funções entre crases (ex.: `app.js`, `registerModule()`). Cite apenas arquivos presentes no contexto. "
          "Se o contexto não bastar, diga exatamente o que não foi possível determinar (\"Encontrei X, mas não consegui determinar Y\" "
          "ou \"Não encontrei isso no índice\"). Nunca invente arquivos, funções ou relações.")
