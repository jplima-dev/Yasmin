"""Busca por relevância (BM25) restrita a UM caderno.

Etapas: normaliza a consulta -> expande prefixos existentes no índice -> BM25 sobre os trechos
-> bônus por cobertura de termos e por frase exata -> monta trechos com destaque.
Cada resultado preserva metadados (caderno, arquivo, linhas) para citação futura (RAG).
"""
import html
import math
import re
import time
from collections import Counter, defaultdict
from functools import lru_cache

from .chunker import heading_before
from .text import fold, tokenize

K1, B = 1.4, 0.75
_WORD = re.compile(r"\w+")


@lru_cache(maxsize=16384)
def _word_tokens(word: str):
    return tuple(tokenize(word))


def _spans(line, matched):
    return [(m.start(), m.end()) for m in _WORD.finditer(line)
            if any(t in matched for t in _word_tokens(m.group()))]


def _mark(line, matched, width=240):
    spans = _spans(line, matched)
    start = max(0, spans[0][0] - 80) if spans and len(line) > width else 0
    seg = line[start:start + width]
    out, pos = [], 0
    for s, e in _spans(seg, matched):
        out += [html.escape(seg[pos:s]), "<mark>", html.escape(seg[s:e]), "</mark>"]
        pos = e
    out.append(html.escape(seg[pos:]))
    return ("…" if start else "") + "".join(out) + ("…" if start + width < len(line) else "")


def _snippet(text, start_line, matched):
    lines = text.split("\n")
    counts = [len(_spans(l, matched)) for l in lines]
    best = max(range(len(lines)), key=lambda i: (counts[i], -i))
    out = []
    for i in range(max(0, best - 1), min(len(lines), best + 3)):
        if lines[i].strip() or i == best:
            out.append({"n": start_line + i, "html": _mark(lines[i], matched)})
    return best + start_line, out


def _expand(conn, nb, qtokens):
    weights = {t: (1.0, t) for t in qtokens}  # termo -> (peso, termo original da consulta)
    for t in qtokens:
        if len(t) >= 3:
            rows = conn.execute("SELECT DISTINCT term FROM postings WHERE notebook_id=? AND term>=? AND term<? "
                                "LIMIT 25", (nb, t, t + "\uffff")).fetchall()
            for (r,) in rows:
                weights.setdefault(r, (0.5, t))
    return weights


def search(conn, notebook, query, limit=20):
    t0 = time.perf_counter()
    nb = notebook["id"]
    res = {"query": query, "notebook_id": nb, "hits": [], "files": [], "total": 0, "reason": None}
    qtokens = list(dict.fromkeys(tokenize(query)))
    if not qtokens:
        return {**res, "reason": "no_terms"}
    N, total_len = conn.execute("SELECT COUNT(*), COALESCE(SUM(length),0) FROM chunks WHERE notebook_id=?",
                                (nb,)).fetchone()
    if N == 0:
        return {**res, "reason": "empty_notebook"}
    avgdl = total_len / N

    weights = _expand(conn, nb, qtokens)
    terms = list(weights)
    rows = conn.execute("SELECT p.chunk_id, p.term, p.tf, c.length FROM postings p JOIN chunks c ON c.id=p.chunk_id "
                        f"WHERE p.notebook_id=? AND p.term IN ({','.join('?' * len(terms))})",
                        [nb, *terms]).fetchall()
    df = Counter(r["term"] for r in rows)
    scores, covered = defaultdict(float), defaultdict(set)
    for r in rows:
        w, origin = weights[r["term"]]
        d = df[r["term"]]
        idf = math.log(1 + (N - d + 0.5) / (d + 0.5))
        tf = r["tf"]
        scores[r["chunk_id"]] += w * idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * r["length"] / avgdl))
        covered[r["chunk_id"]].add(origin)
    if not scores:
        return {**res, "reason": "no_match", "took_ms": round((time.perf_counter() - t0) * 1000)}
    for cid in scores:
        scores[cid] *= 1 + len(covered[cid]) / len(qtokens)

    cand = sorted(scores, key=scores.get, reverse=True)[:60]
    chunks = conn.execute("SELECT c.*, d.filename, d.ext FROM chunks c JOIN documents d ON d.id=c.document_id "
                          f"WHERE c.id IN ({','.join('?' * len(cand))})", cand).fetchall()
    phrase = fold(query).strip()
    if len(qtokens) >= 2:
        for c in chunks:
            if phrase in fold(c["text"]):
                scores[c["id"]] *= 1.3

    matched = set(terms)
    hits = []
    for c in sorted(chunks, key=lambda c: scores[c["id"]], reverse=True)[:limit]:
        line, snip = _snippet(c["text"], c["start_line"], matched)
        hits.append({
            "chunk_id": c["id"], "notebook_id": nb, "notebook": notebook["name"],
            "document_id": c["document_id"], "filename": c["filename"], "ext": c["ext"],
            "start_line": c["start_line"], "end_line": c["end_line"], "line": line,
            "heading": heading_before(c["text"].split("\n"), line - c["start_line"], c["ext"], c["heading"]),
            "score": round(scores[c["id"]], 2),
            "snippet": snip, "text": c["text"],  # "text" é para o RAG; a API remove antes de enviar
        })
    files = Counter((h["document_id"], h["filename"]) for h in hits)
    res.update(hits=hits, total=len(scores), files=[{"document_id": k[0], "filename": k[1], "count": v}
                                                    for k, v in files.most_common()],
               took_ms=round((time.perf_counter() - t0) * 1000), reason=None)
    return res
