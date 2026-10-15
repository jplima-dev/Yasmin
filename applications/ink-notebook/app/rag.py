"""Ponto de extensão para um futuro RAG local (NÃO há LLM conectada hoje).

Para ligar um modelo local (Ollama, llama.cpp...), implemente um LLMProvider e devolva-o em
get_provider(). A busca já devolve trechos com caderno, arquivo e linhas; build_prompt() os
numera [1], [2]... para o modelo poder citá-los, e answer() devolve resposta + fontes.
"""
from typing import Protocol


class LLMProvider(Protocol):
    name: str

    def generate(self, prompt: str) -> str: ...


def get_provider() -> LLMProvider | None:
    return None  # TODO: instanciar um provedor local aqui


def build_context(hits: list[dict], max_hits: int = 6) -> str:
    return "\n\n".join(
        f"[{i}] {h['notebook']} / {h['filename']} (linhas {h['start_line']}-{h['end_line']})\n{h['text']}"
        for i, h in enumerate(hits[:max_hits], 1))


def build_prompt(question: str, hits: list[dict]) -> str:
    return ("Responda à pergunta usando APENAS as fontes abaixo e cite-as como [n]. "
            "Se as fontes não bastarem, diga isso.\n\n"
            f"FONTES:\n{build_context(hits)}\n\nPERGUNTA: {question}\n")


def answer(question: str, hits: list[dict]) -> dict:
    provider = get_provider()
    if provider is None:
        return {"enabled": False, "reason": "Nenhum modelo local configurado: a busca mostra trechos das fontes."}
    text = provider.generate(build_prompt(question, hits))
    sources = [{"n": i, "filename": h["filename"], "start_line": h["start_line"], "end_line": h["end_line"],
                "document_id": h["document_id"]} for i, h in enumerate(hits[:6], 1)]
    return {"enabled": True, "provider": provider.name, "text": text, "sources": sources}
