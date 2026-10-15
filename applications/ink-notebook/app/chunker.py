"""Divide o documento em trechos úteis, preservando faixa de linhas e título da seção."""
import re

_MD_HEAD = re.compile(r"^\s{0,3}#{1,6}\s+(.*\S)")
_CODE_HEAD = re.compile(r"^\s*(?:async\s+)?(?:def|class|function)\s+([\w$]+)")
TARGET_CHARS = 900
MAX_LINES = 40
OVERLAP = 2


def _headings(lines, ext):
    rx = _CODE_HEAD if ext in (".py", ".js", ".mjs", ".ts", ".tsx", ".jsx") else _MD_HEAD
    cur, out = "", []
    for ln in lines:
        m = rx.match(ln)
        if m:
            cur = m.group(1).strip()[:120]
        out.append(cur)
    return out


def heading_before(lines, idx, ext, default=""):
    """Título da seção mais próximo ANTES da linha idx (dentro das linhas dadas)."""
    rx = _CODE_HEAD if ext in (".py", ".js", ".mjs", ".ts", ".tsx", ".jsx") else _MD_HEAD
    for i in range(idx, -1, -1):
        m = rx.match(lines[i])
        if m:
            return m.group(1).strip()[:120]
    return default


def chunk_lines(lines: list[str], ext: str = "") -> list[dict]:
    heads = _headings(lines, ext)
    is_md_head = lambda l: bool(_MD_HEAD.match(l)) and ext in (".md", ".markdown", ".txt", ".rst", "")
    n, s, chunks = len(lines), 0, []
    while s < n:
        e, size, broke_on_head = s, 0, False
        while e < n and e - s < MAX_LINES:
            if e > s and is_md_head(lines[e]) and size > 200:
                broke_on_head = True
                break
            if e > s and size + len(lines[e]) > TARGET_CHARS:
                break
            size += len(lines[e]) + 1
            e += 1
        text = "\n".join(lines[s:e])
        if text.strip():
            chunks.append({"start_line": s + 1, "end_line": e, "heading": heads[s], "text": text})
        if e >= n:
            break
        s = e if broke_on_head else max(e - OVERLAP, s + 1)
    return chunks
