"""Perguntas em linguagem natural: 1) intenções estruturais respondidas SEM IA; 2) recuperação de contexto; 3) IA opcional."""
import json
import re

from .. import db
from ..text import STOP, fold
from . import ai, query, rules, synonyms

COMMON = set("""onde como qual quais quem quando porque por que arquivo arquivos funcao funcoes classe classes metodo
metodos modulo modulos projeto codigo isso esse essa aqui eu me mostra mostre explica explique fluxo importa importado
chama chamada usado usada usa fica esta estao existem quantas quantos tem possui define definido mudar alterar quebrar
novo nova outro outra igual envolvidos responsavel todos todas pode posso preciso precisaria adiciono adicionar criar
coloco colocar fazer faco funciona sistema controla clico clicar botao acontece quando depende dependencias""".split())
TOKEN = re.compile(r"[`'\"]?([\w./\\\-]{2,})(\(\))?[`'\"]?")


def entities(conn, nb, question):
    """Acha arquivos e símbolos citados na pergunta."""
    files, syms, seen = [], [], set()
    for m in TOKEN.finditer(question):
        tok, quoted = m.group(1).strip(".,;:?!"), question[m.start()] in "`'\"" or bool(m.group(2))
        low = fold(tok)
        if len(low) < 3 or low in seen:
            continue
        seen.add(low)
        codey = quoted or "." in tok or "/" in tok or "_" in tok or "-" in tok or (tok != tok.lower() and tok != tok.capitalize())
        if low in COMMON or low in STOP:
            continue
        fs = query.find_files(conn, nb, tok) if (codey or len(low) >= 4) else []
        if fs and (codey or len(fs) <= 3):
            files += [f for f in fs if f["id"] not in {x["id"] for x in files}]
            continue
        ss = query.symbols_named(conn, nb, tok.rstrip("()"))
        if ss and (codey or len(ss) <= 4):
            syms.append((tok.rstrip("()"), ss))
    return files, syms


def _p(path, line=None):
    return f"`{path}`" + (f" (linha {line})" if line else "")


def _src(path, line=None, end=None, why=""):
    return {"path": path, "start": line, "end": end or line, "reason": why}


def structural(conn, nb, question):
    """Tenta responder só com o índice. Devolve dict ou None (aí segue para recuperação + IA)."""
    q = fold(question)
    files, syms = entities(conn, nb, question)
    callable_syms = [(n, ss) for n, ss in syms if any(s["kind"] in query.CALLABLE for s in ss)] or syms

    if re.search(r"quantas?|quantos", q) and re.search(r"funco|classe|metodo|simbolo|arquivo|linha|pasta", q):
        kind = ("function" if "funco" in q else "class" if "classe" in q else "method" if "metodo" in q else None)
        if kind and files:
            f = files[0]
            n = conn.execute("SELECT COUNT(*) FROM code_symbols WHERE file_id=? AND kind=?", (f["id"], kind)).fetchone()[0]
            return {"text": f"`{f['path']}` define **{n}** {'função(ões)' if kind == 'function' else 'classe(s)' if kind == 'class' else 'método(s)'}.",
                    "sources": [_src(f["path"], why="contagem no índice")]}
        ov = query.overview(conn, nb)
        return {"text": f"O projeto indexado tem **{ov['files']}** arquivos em **{ov['folders']}** pastas, "
                        f"**{ov['symbols']}** símbolos e cerca de **{ov['lines']}** linhas.", "sources": []}

    if re.search(r"quebrar|afetad|impact|se eu (mudar|alterar|apagar|remover|renomear|trocar)", q) and (files or syms):
        out, sources = [], []
        if files:
            f = files[0]
            dep = query.transitive_importers(conn, nb, f["id"])
            direct = [d for d in dep if d["depth"] == 1]
            out.append(f"Se você mudar `{f['path']}`, o índice mostra **{len(direct)}** arquivo(s) que dependem dele diretamente"
                       f" e **{len(dep)}** no total (contando dependências indiretas).")
            out += [f"- `{d['path']}`" + (" (indireto)" if d["depth"] > 1 else "") for d in dep[:25]]
            sources += [_src(d["path"], why="depende do arquivo") for d in dep[:8]]
            if not dep:
                out.append("Nenhum outro arquivo o importa. Atenção: referências dinâmicas (strings, eventos, HTML) podem não ter sido detectadas.")
        else:
            name, ss = callable_syms[0]
            cs = query.callers_of(conn, nb, name)
            out.append(f"`{name}` é chamada em **{len(cs)}** ponto(s) do projeto; mudar sua assinatura ou comportamento pode afetar:")
            out += [f"- {_p(c['path'], c['line'])}" + (f" dentro de `{c['in']}`" if c["in"] else "") for c in cs[:25]]
            sources += [_src(c["path"], c["line"], why="chama a função") for c in cs[:8]]
        out.append("\n_Limite: só relações estáticas detectadas pelo indexador. Chamadas dinâmicas podem não aparecer._")
        return {"text": "\n".join(out), "sources": sources}

    if re.search(r"quem (chama|invoca|executa)|onde .*(e|esta|sao|foi) (usad|chamad)|onde (.* )?(usa|chama)|mostra onde .* (e|é) usad", q) and callable_syms:
        name, ss = callable_syms[0]
        cs = query.callers_of(conn, nb, name)
        defs = [s for s in ss if s["kind"] in query.CALLABLE]
        head = f"`{name}` é definida em " + ", ".join(_p(s["path"], s["line"]) for s in defs[:3]) + "." if defs else f"Não encontrei a definição de `{name}` no índice."
        if not cs:
            return {"text": head + "\nNão encontrei chamadas a ela no índice (pode ser usada dinamicamente, por evento ou string).",
                    "sources": [_src(s["path"], s["line"], s["end_line"], "definição") for s in defs[:3]]}
        lines = [head, f"\nChamadas encontradas (**{len(cs)}**):"]
        lines += [f"- {_p(c['path'], c['line'])}" + (f" em `{c['in']}`" if c["in"] else "") for c in cs[:30]]
        return {"text": "\n".join(lines),
                "sources": [_src(s["path"], s["line"], s["end_line"], "definição") for s in defs[:2]] + [_src(c["path"], c["line"], why="chamada") for c in cs[:8]]}

    if re.search(r"quem (importa|usa|depende|referencia|carrega)|(importad|usad|referenciad)[oa] (por|em)", q) and files:
        f = files[0]
        im = query.importers(conn, nb, f["id"])
        if not im:
            return {"text": f"Nenhum arquivo importa `{f['path']}` no índice (pode ser um ponto de entrada ou ser carregado dinamicamente).",
                    "sources": [_src(f["path"])]}
        return {"text": f"`{f['path']}` é importado/referenciado por **{len(im)}** arquivo(s):\n" +
                        "\n".join(f"- {_p(r['path'], r['line'])}" for r in im[:40]),
                "sources": [_src(r["path"], r["line"], why="importa o arquivo") for r in im[:10]]}

    if re.search(r"(o que|quais?|de que) .*(importa|depende|usa)|dependencias de", q) and files:
        f = files[0]
        internal, external = query.imports_of(conn, nb, f["id"])
        lines = [f"`{f['path']}` depende de **{len(internal)}** arquivo(s) do projeto" + (f" e de {len(external)} biblioteca(s) externa(s)." if external else ".")]
        lines += [f"- {_p(r['path'], r['line'])}" for r in internal[:30]]
        if external:
            lines.append("\nExternas: " + ", ".join(f"`{e}`" for e in external[:20]))
        return {"text": "\n".join(lines), "sources": [_src(r["path"], r["line"], why="é importado") for r in internal[:10]]}

    if re.search(r"qual arquivo (possui|tem|define|contem)|onde (fica|esta|estao|e definid|foi definid)|em que arquivo|onde .*(definid|declarad)", q) and (syms or files):
        if syms:
            name, ss = syms[0]
            lines = [f"`{name}` aparece em:"] + [f"- {_p(s['path'], s['line'])} — {s['kind']}" + (f" de `{s['parent']}`" if s["parent"] else "") for s in ss[:12]]
            return {"text": "\n".join(lines), "sources": [_src(s["path"], s["line"], s["end_line"], f"define {s['kind']}") for s in ss[:6]]}
        f = files[0]
        return {"text": f"O arquivo está em `{f['path']}` ({f['lines']} linhas).", "sources": [_src(f["path"])]}

    if re.search(r"pontos? de entrada|por onde (comeca|inicia)", q):
        ov = query.overview(conn, nb)
        eps = ov["entry_points"]
        if eps:
            return {"text": "Possíveis pontos de entrada detectados:\n" + "\n".join(f"- `{e['path']}`" + (f" — {e['doc']}" if e["doc"] else "") for e in eps),
                    "sources": [_src(e["path"]) for e in eps[:8]]}
    if re.search(r"quais (sao os )?modulos|lista (de )?modulos", q):
        ms = query.modules(conn, nb)
        return {"text": "Módulos/pastas principais:\n" + "\n".join(f"- `{m['module']}` — {m['files']} arquivos, {m['symbols']} funções/classes" + (f" · {m['doc']}" if m["doc"] else "") for m in ms[:30]),
                "sources": []}
    return None


# ------------------------------------------------------------------ recuperação de contexto
def _outline(conn, fid, limit=22):
    rows = conn.execute("SELECT name, kind, parent, line FROM code_symbols WHERE file_id=? AND kind IN ('function','class','method','route','variable','heading') "
                        "ORDER BY line LIMIT ?", (fid, limit)).fetchall()
    return ", ".join((f"{r['parent']}." if r["parent"] and r["kind"] == "method" else "") + r["name"] + f"@{r['line']}" for r in rows)


def _topic(question):
    """Tira palavras de pergunta ('onde', 'qual', 'arquivo'...) para a busca focar no assunto."""
    words = [w for w in re.findall(r"[\w$.-]+", question) if fold(w) not in synonyms.QUESTION_WORDS and fold(w) not in STOP]
    return " ".join(words) or question


def build_context(conn, nb, question, max_chars):
    """Seleciona poucos arquivos relevantes (+ vizinhos no grafo) e monta trechos pequenos. Nunca o projeto inteiro."""
    res = query.search(conn, nb, _topic(question), limit=8)
    hits = [h for h in res["hits"] if h["score"] >= 3]  # abaixo disso é ruído: melhor dizer que não achou
    entries, used = [], 0
    chosen = {h["path"]: h for h in hits}
    for h in hits[:3]:  # vizinhos diretos dos melhores resultados
        f = query.get_file(conn, nb, h["path"])
        internal, _ = query.imports_of(conn, nb, f["id"])
        for r in (internal[:2] + list(query.importers(conn, nb, f["id"]))[:1]):
            if r["path"] not in chosen and len(chosen) < 10:
                chosen[r["path"]] = {"path": r["path"], "why": [f"relacionado a {h['path']} (import)"], "line": None, "snippet": [], "score": 0}
    for path, h in chosen.items():
        if used >= max_chars:
            break
        f = query.get_file(conn, nb, path)
        if not f or f["secret"]:
            continue
        internal, external = query.imports_of(conn, nb, f["id"])
        used_by = query.importers(conn, nb, f["id"])
        head = [f"### {path} ({f['lang']}, {f['lines']} linhas)"]
        if f["doc"]:
            head.append(f"Resumo: {f['doc']}")
        head.append("Importa: " + (", ".join(r["path"] for r in internal[:8]) or "—"))
        head.append("Usado por: " + (", ".join(r["path"] for r in used_by[:8]) or "—"))
        head.append("Símbolos: " + (_outline(conn, f["id"]) or "—"))
        chunks = conn.execute("SELECT start_line, end_line, text FROM code_chunks WHERE file_id=? ORDER BY start_line", (f["id"],)).fetchall()
        pick = [c for c in chunks if h.get("line") and c["start_line"] <= h["line"] <= c["end_line"]] or chunks[:1]
        body, ranges = [], []
        for c in pick[:2]:
            txt = rules.redact(c["text"])[:1500]
            body.append(f"```\n{txt}\n```  (linhas {c['start_line']}–{c['end_line']})")
            ranges.append((c["start_line"], c["end_line"]))
        block = "\n".join(head + body)
        if used + len(block) > max_chars and entries:
            continue
        entries.append({"path": path, "ranges": ranges, "why": h["why"], "text": block[:max_chars], "score": h.get("score", 0)})
        used += len(block)
    return entries


def _plain_answer(conn, nb, question, entries):
    top = entries[:6]
    lines = ["Encontrei estes arquivos relacionados à sua pergunta (resposta montada só com o índice local, sem IA):", ""]
    for i, e in enumerate(top, 1):
        f = query.get_file(conn, nb, e["path"])
        d = f"`{e['path']}`" + (f" — {f['doc']}" if f["doc"] else "")
        lines.append(f"{i}. {d}")
        lines.append(f"   _por que apareceu:_ {'; '.join(e['why'][:2])}")
    first = query.get_file(conn, nb, top[0]["path"])
    used_by = query.importers(conn, nb, first["id"])
    internal, _ = query.imports_of(conn, nb, first["id"])
    lines.append("")
    if internal or used_by:
        lines.append(f"Relações de `{first['path']}`: importa {len(internal)} arquivo(s) do projeto e é usado por {len(used_by)}.")
    lines.append("Para uma explicação em linguagem natural conectando esses pontos, configure uma IA (⚙ IA). Não afirmo nada além do que o índice detectou.")
    return "\n".join(lines)


def ask(conn, nb, question, confirm=False, dry_run=False):
    settings = ai.load_settings(conn)
    st = structural(conn, nb, question)
    if st:
        return {"mode": "index", "kind": "structural", **st}
    max_chars = max(2000, min(int(settings["ctx_max_chars"] or 12000), 60000))
    entries = build_context(conn, nb, question, max_chars)
    if not entries:
        return {"mode": "index", "kind": "empty", "text": "Não encontrei isso no índice. Tente outros termos (nome de função, arquivo ou conceito) "
                                                       "ou importe mais arquivos.", "sources": []}
    sources = [{"path": e["path"], "start": e["ranges"][0][0] if e["ranges"] else None,
                "end": e["ranges"][0][1] if e["ranges"] else None, "reason": "; ".join(e["why"][:2])} for e in entries]
    provider = ai.get_provider(settings)
    if provider is None:
        return {"mode": "index", "kind": "retrieval", "text": _plain_answer(conn, nb, question, entries), "sources": sources}
    sent = [{"path": e["path"], "ranges": e["ranges"]} for e in entries]
    if provider.external and settings["review_external"] == "1" and not confirm:
        return {"mode": "needs_confirmation", "provider": provider.name, "sent": sent, "chars": sum(len(e["text"]) for e in entries),
                "sources": sources, "text": ""}
    if dry_run:
        return {"mode": "needs_confirmation", "provider": provider.name, "sent": sent, "sources": sources, "text": ""}
    prompt = ("CONTEXTO RECUPERADO DO ÍNDICE:\n\n" + "\n\n".join(e["text"] for e in entries) + f"\n\nPERGUNTA DO USUÁRIO: {question}\n")
    try:
        text = provider.generate(ai.SYSTEM, prompt)
    except ai.AIError as e:
        return {"mode": "index", "kind": "retrieval", "warning": f"A IA falhou: {e}. Mostrando só o índice local.",
                "text": _plain_answer(conn, nb, question, entries), "sources": sources}
    return {"mode": "ai", "provider": provider.name, "external": provider.external, "text": text, "sources": sources, "sent": sent}


_BT = re.compile(r"`([^`\n]{2,120})`")


def make_links(conn, nb, text):
    """Para cada `termo` na resposta que existe no índice, devolve onde abrir (arquivo/linha)."""
    links = {}
    for m in _BT.finditer(text or ""):
        label = m.group(1)
        if label in links:
            continue
        tok = re.split(r"\s+[(→-]|\(", label)[0].strip()
        fs = query.find_files(conn, nb, tok) if re.search(r"[./]|\w\.\w", tok) or True else []
        if fs and len(fs) == 1:
            links[label] = {"path": fs[0]["path"], "line": None}
            continue
        name = tok.split("→")[-1].split(".")[-1].rstrip("()").strip()
        ss = query.symbols_named(conn, nb, name) if re.match(r"^[\w$]+$", name) else []
        if ss:
            links[label] = {"path": ss[0]["path"], "line": ss[0]["line"]}
    return links


def log_history(conn, nb, question, result):
    conn.execute("INSERT INTO code_history(notebook_id,ts,question,mode,answer) VALUES(?,?,?,?,?)",
                 (nb, db.now(), question, result["mode"], json.dumps({k: result.get(k) for k in ("text", "sources", "provider", "kind", "warning")})))
    conn.execute("DELETE FROM code_history WHERE notebook_id=? AND id NOT IN (SELECT id FROM code_history WHERE notebook_id=? ORDER BY id DESC LIMIT 200)", (nb, nb))
