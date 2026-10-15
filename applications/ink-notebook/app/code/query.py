"""Consultas sobre o índice: busca com motivos, relações, grafo, visão geral. Tudo determinístico (sem IA)."""
import json
import posixpath
import re
from collections import Counter, defaultdict, deque

from .. import db
from ..search import _snippet
from ..text import fold, tokenize
from . import synonyms

CALLABLE = ("function", "class", "method")


# ------------------------------------------------------------------ localizar entidades
def get_file(conn, nb, ref=None, fid=None):
    if fid:
        return conn.execute("SELECT * FROM code_files WHERE id=? AND notebook_id=?", (fid, nb)).fetchone()
    return conn.execute("SELECT * FROM code_files WHERE notebook_id=? AND path=?", (nb, ref)).fetchone()


def find_files(conn, nb, ref):
    """Casa 'app.js', 'modules/x/index.js' ou 'module-loader' com arquivos do projeto."""
    ref = (ref or "").strip().strip("`'\"").replace("\\", "/").lstrip("./")
    if not ref:
        return []
    rows = conn.execute("SELECT id, path, lang, lines FROM code_files WHERE notebook_id=?", (nb,)).fetchall()
    low = ref.lower()
    exact = [r for r in rows if r["path"].lower() == low]
    if exact:
        return exact
    end = [r for r in rows if r["path"].lower().endswith("/" + low)]
    if end:
        return end
    base = [r for r in rows if posixpath.basename(r["path"]).lower() == low]
    if base:
        return base
    if "." not in low.rsplit("/", 1)[-1]:
        stem = [r for r in rows if posixpath.splitext(posixpath.basename(r["path"]))[0].lower() == low]
        if stem:
            return stem
    return []


def symbols_named(conn, nb, name, kinds=None):
    q = ("SELECT s.*, f.path FROM code_symbols s JOIN code_files f ON f.id=s.file_id "
         "WHERE s.notebook_id=? AND s.name=? COLLATE NOCASE")
    args = [nb, name]
    if kinds:
        q += f" AND s.kind IN ({','.join('?' * len(kinds))})"
        args += list(kinds)
    return conn.execute(q + " ORDER BY f.path, s.line LIMIT 40", args).fetchall()


def importers(conn, nb, fid, kinds=("imports", "references")):
    return conn.execute(
        "SELECT f.id, f.path, MIN(e.line) AS line, e.kind FROM code_edges e JOIN code_files f ON f.id=e.src_id "
        f"WHERE e.dst_id=? AND e.kind IN ({','.join('?' * len(kinds))}) GROUP BY f.id ORDER BY f.path", (fid, *kinds)).fetchall()


def imports_of(conn, nb, fid):
    internal = conn.execute(
        "SELECT f.id, f.path, MIN(e.line) AS line FROM code_edges e JOIN code_files f ON f.id=e.dst_id "
        "WHERE e.src_id=? AND e.kind IN ('imports','references') GROUP BY f.id ORDER BY f.path", (fid,)).fetchall()
    external = conn.execute(
        "SELECT DISTINCT target FROM code_edges WHERE src_id=? AND kind='imports' AND dst_id IS NULL ORDER BY target", (fid,)).fetchall()
    return internal, [r["target"] for r in external]


def callers_of(conn, nb, name):
    """Quem chama `name`: (arquivo, linha, função que contém a chamada)."""
    refs = conn.execute("SELECT r.file_id, r.line, f.path FROM code_refs r JOIN code_files f ON f.id=r.file_id "
                        "WHERE r.notebook_id=? AND r.name=? AND r.kind='call' ORDER BY f.path, r.line", (nb, name)).fetchall()
    defs = {(s["file_id"], s["line"]) for s in symbols_named(conn, nb, name, CALLABLE)}
    out, enc_cache = [], {}
    for r in refs:
        if (r["file_id"], r["line"]) in defs:
            continue
        if r["file_id"] not in enc_cache:
            enc_cache[r["file_id"]] = conn.execute(
                "SELECT name, line, end_line, kind, parent FROM code_symbols WHERE file_id=? AND kind IN ('function','method','class') "
                "ORDER BY line", (r["file_id"],)).fetchall()
        inside = [s for s in enc_cache[r["file_id"]] if s["line"] <= r["line"] <= s["end_line"]]
        enc = min(inside, key=lambda s: s["end_line"] - s["line"]) if inside else None
        out.append({"file_id": r["file_id"], "path": r["path"], "line": r["line"],
                    "in": (f"{enc['parent']}.{enc['name']}" if enc and enc["parent"] else enc["name"]) if enc else None})
    return out


def transitive_importers(conn, nb, fid, limit=80):
    """Quem depende (direta ou indiretamente) de um arquivo: base da pergunta 'o que pode quebrar?'."""
    seen, order, dq = {fid: 0}, [], deque([fid])
    while dq and len(order) < limit:
        cur = dq.popleft()
        rows = conn.execute("SELECT DISTINCT f.id, f.path FROM code_edges e JOIN code_files f ON f.id=e.src_id "
                            "WHERE e.dst_id=? AND e.notebook_id=?", (cur, nb)).fetchall()
        for r in rows:
            if r["id"] not in seen:
                seen[r["id"]] = seen[cur] + 1
                order.append({"id": r["id"], "path": r["path"], "depth": seen[cur] + 1})
                dq.append(r["id"])
    return order


# ------------------------------------------------------------------ busca
def _qtokens(q):
    toks = list(dict.fromkeys(tokenize(q)))
    extra = [t for x in synonyms.expand(fold(q)) for t in tokenize(x)]
    return toks, [t for t in dict.fromkeys(extra) if t not in toks]


def search(conn, nb, q, limit=25):
    """Busca híbrida: caminho + símbolos + texto (FTS/BM25) + ids/classes. Cada resultado traz POR QUE apareceu."""
    toks, extra = _qtokens(q)
    allt = toks + extra
    if not allt:
        return {"query": q, "hits": [], "reason": "no_terms", "terms": []}
    score, reasons, best = defaultdict(float), defaultdict(list), {}
    files = {r["id"]: r for r in conn.execute("SELECT id, path, lang, lines, doc FROM code_files WHERE notebook_id=?", (nb,))}

    def add(fid, pts, why):
        if fid in files:
            score[fid] += pts
            if why not in reasons[fid] and len(reasons[fid]) < 5:
                reasons[fid].append(why)

    for fid, f in files.items():  # nome/caminho
        ptoks = set(tokenize(f["path"]))
        name_toks = set(tokenize(posixpath.basename(f["path"])))
        w = [t for t in allt if t in ptoks]
        if w:
            add(fid, sum(3 if t in name_toks else 1.2 for t in w) * (1 if set(toks) & set(w) else .6),
                f"caminho contém {', '.join(w)}")
    exact = q.strip().strip("`'\"").rstrip("()")
    for s in symbols_named(conn, nb, exact) if exact and " " not in exact else []:
        add(s["file_id"], 8, f"define {s['kind']} `{s['name']}` (linha {s['line']})")
    marks = ",".join("?" * len(allt))
    for s in conn.execute("SELECT s.file_id, s.name, s.kind, s.line FROM code_symbols s WHERE s.notebook_id=? LIMIT 20000", (nb,)):
        st = tokenize(s["name"])
        hit = [t for t in allt if t in st]
        if hit and (set(toks) & set(hit) or len(hit) >= 2):
            add(s["file_id"], 2.5 * len(hit) / max(len(st), 1) + 1, f"{s['kind']} `{s['name']}` (linha {s['line']})")
    if db.has_fts(conn):
        fq = " OR ".join(f'"{t}"*' for t in allt)
        try:
            rows = conn.execute(
                "SELECT c.id, c.file_id, c.start_line, c.end_line, c.text, bm25(code_fts) AS r FROM code_fts "
                "JOIN code_chunks c ON c.id=code_fts.rowid WHERE code_fts MATCH ? AND c.notebook_id=? ORDER BY r LIMIT 120",
                (fq, nb)).fetchall()
        except Exception:
            rows = []
    else:
        like = " OR ".join("c.text LIKE ?" for _ in allt)
        rows = conn.execute(f"SELECT c.id, c.file_id, c.start_line, c.end_line, c.text, -1.0 AS r FROM code_chunks c "
                            f"WHERE c.notebook_id=? AND ({like}) LIMIT 120", [nb, *[f"%{t}%" for t in allt]]).fetchall()
    matched = set(allt)
    for r in rows:
        pts = min(-r["r"], 12)
        folded = fold(r["text"])
        cov = sum(1 for t in toks if t in folded)
        add(r["file_id"], pts * (1 + cov / max(len(toks), 1) * 0.5) * 0.5,
            f"texto nas linhas {r['start_line']}–{r['end_line']}")
        if r["file_id"] not in best or best[r["file_id"]][0] < pts:
            best[r["file_id"]] = (pts, r)
    for ref in conn.execute(f"SELECT DISTINCT file_id, name, kind, MIN(line) AS line FROM code_refs WHERE notebook_id=? AND kind IN ('id','css-var') "
                            f"AND name COLLATE NOCASE IN ({marks}) GROUP BY file_id, name", [nb, *allt]):
        add(ref["file_id"], 1.5, f"referencia {ref['kind']} `{ref['name']}`")
    hits = []
    for fid, sc in sorted(score.items(), key=lambda kv: kv[1], reverse=True)[:limit]:
        f = files[fid]
        hit = {"file_id": fid, "path": f["path"], "lang": f["lang"], "score": round(sc, 1), "why": reasons[fid],
               "doc": f["doc"], "line": None, "snippet": []}
        if fid in best:
            r = best[fid][1]
            line, snip = _snippet(r["text"], r["start_line"], matched)
            hit["line"], hit["snippet"] = line, snip
        hits.append(hit)
    return {"query": q, "hits": hits, "terms": toks, "extra_terms": extra, "total": len(score),
            "reason": None if hits else "no_match"}


# ------------------------------------------------------------------ arquivo / grafo
def file_detail(conn, nb, f):
    syms = conn.execute("SELECT name, kind, parent, line, end_line, sig FROM code_symbols WHERE file_id=? ORDER BY line", (f["id"],)).fetchall()
    internal, external = imports_of(conn, nb, f["id"])
    used = importers(conn, nb, f["id"])
    called = conn.execute("SELECT DISTINCT e.target, s.path FROM code_edges e JOIN code_files s ON s.id=e.src_id "
                          "WHERE e.dst_id=? AND e.kind='calls' ORDER BY s.path", (f["id"],)).fetchall()
    return {"id": f["id"], "path": f["path"], "lang": f["lang"], "lines": f["lines"], "size": f["size"], "doc": f["doc"],
            "entry": bool(f["entry"]), "secret": bool(f["secret"]), "exports": json.loads(f["exports"]),
            "symbols": [dict(s) for s in syms],
            "imports": [dict(r) for r in internal], "external": external,
            "used_by": [dict(r) for r in used],
            "called_by": [{"path": r["path"], "name": r["target"]} for r in called]}


def graph(conn, nb, root=None, depth=1, direction="both", kinds=("imports", "references", "calls"), limit=60):
    """Grafo em torno de um arquivo (BFS limitado). Sem raiz: visão por pastas (módulos)."""
    kinds = tuple(kinds)
    if root is None:
        return module_graph(conn, nb, kinds)
    nodes, edges, dq = {root: 0}, set(), deque([(root, 0)])
    while dq:
        cur, d = dq.popleft()
        if d >= depth:
            continue
        q = []
        if direction in ("both", "out"):
            q.append(("SELECT src_id AS a, dst_id AS b, kind FROM code_edges WHERE src_id=? AND dst_id IS NOT NULL", cur))
        if direction in ("both", "in"):
            q.append(("SELECT src_id AS a, dst_id AS b, kind FROM code_edges WHERE dst_id=?", cur))
        for sql, p in q:
            for r in conn.execute(sql, (p,)):
                if r["kind"] not in kinds:
                    continue
                other = r["b"] if r["a"] == cur else r["a"]
                if other not in nodes and len(nodes) >= limit:
                    continue
                edges.add((r["a"], r["b"], r["kind"]))
                if other not in nodes:
                    nodes[other] = d + 1
                    dq.append((other, d + 1))
    info = {r["id"]: r for r in conn.execute(f"SELECT id, path, lang FROM code_files WHERE id IN ({','.join('?' * len(nodes))})", list(nodes))}
    return {"root": root, "nodes": [{"id": i, "path": info[i]["path"], "lang": info[i]["lang"], "depth": d}
                                    for i, d in nodes.items() if i in info],
            "edges": [{"src": a, "dst": b, "kind": k} for a, b, k in edges if a in info and b in info],
            "truncated": len(nodes) >= limit}


def _group(path, level=2):
    parts = path.split("/")
    return "/".join(parts[:level]) if len(parts) > level else ("/".join(parts[:-1]) or "(raiz)")


def module_graph(conn, nb, kinds, level=None):
    paths = {r["id"]: r["path"] for r in conn.execute("SELECT id, path FROM code_files WHERE notebook_id=?", (nb,))}
    level = level or (1 if len({p.split("/")[0] for p in paths.values()}) > 3 else 2)
    cnt, w = Counter(), Counter()
    for r in conn.execute("SELECT src_id, dst_id, kind FROM code_edges WHERE notebook_id=? AND dst_id IS NOT NULL", (nb,)):
        if r["kind"] not in kinds or r["src_id"] not in paths or r["dst_id"] not in paths:
            continue
        a, b = _group(paths[r["src_id"]], level), _group(paths[r["dst_id"]], level)
        if a != b:
            w[(a, b)] += 1
    for p in paths.values():
        cnt[_group(p, level)] += 1
    top = w.most_common(60)
    names = {x for e, _ in top for x in e}
    return {"root": None, "group": True, "nodes": [{"id": n, "path": n, "lang": "pasta", "depth": 0, "files": cnt[n]} for n in names],
            "edges": [{"src": a, "dst": b, "kind": "imports", "weight": n} for (a, b), n in top], "truncated": len(w) > 60}


# ------------------------------------------------------------------ visão geral
def overview(conn, nb):
    one = lambda sql, *a: conn.execute(sql, a).fetchone()[0]
    langs = {r["lang"]: r["n"] for r in conn.execute("SELECT lang, COUNT(*) n FROM code_files WHERE notebook_id=? GROUP BY lang ORDER BY n DESC", (nb,))}
    dirs = {posixpath.dirname(r["path"]) for r in conn.execute("SELECT path FROM code_files WHERE notebook_id=?", (nb,))}
    allp = {d for p in dirs for d in [p] + [posixpath.dirname(p[:i]) for i in range(len(p)) if p[i] == "/"] if d}
    hubs = conn.execute("SELECT f.path, COUNT(DISTINCT e.src_id) n FROM code_edges e JOIN code_files f ON f.id=e.dst_id "
                        "WHERE e.notebook_id=? AND e.kind IN ('imports','references') GROUP BY f.id ORDER BY n DESC, f.path LIMIT 12", (nb,)).fetchall()
    entries = conn.execute(
        "SELECT f.path, f.doc, f.entry, (SELECT COUNT(*) FROM code_edges x WHERE x.src_id=f.id AND x.dst_id IS NOT NULL) outs, "
        "(SELECT COUNT(*) FROM code_edges y WHERE y.dst_id=f.id AND y.kind IN ('imports','references')) ins FROM code_files f "
        "WHERE f.notebook_id=? AND f.lang IN ('python','javascript','typescript','html','php') ORDER BY f.path", (nb,)).fetchall()
    eps = [e for e in entries if e["entry"] or re.search(r"(^|/)(run|main|app|index|server|launcher|manage)\.(py|js|ts|html|php)$", e["path"])
           or (e["ins"] == 0 and e["outs"] >= 2)]
    ext = Counter()
    for r in conn.execute("SELECT target FROM code_edges WHERE notebook_id=? AND kind='imports' AND dst_id IS NULL", (nb,)):
        t = r["target"]
        if not t.startswith("."):
            ext[t.split(".")[0] if re.match(r"^[\w.]+$", t) else t.split("/")[0]] += 1
    return {"files": one("SELECT COUNT(*) FROM code_files WHERE notebook_id=?", nb), "folders": len(allp),
            "symbols": one("SELECT COUNT(*) FROM code_symbols WHERE notebook_id=?", nb),
            "edges": one("SELECT COUNT(*) FROM code_edges WHERE notebook_id=? AND dst_id IS NOT NULL", nb),
            "lines": one("SELECT COALESCE(SUM(lines),0) FROM code_files WHERE notebook_id=?", nb),
            "secrets": one("SELECT COUNT(*) FROM code_files WHERE notebook_id=? AND (secret=1 OR secret_lines!='[]')", nb),
            "errors": one("SELECT COUNT(*) FROM code_files WHERE notebook_id=? AND status='erro'", nb),
            "languages": langs, "hubs": [dict(h) for h in hubs], "entry_points": [dict(e) for e in eps[:15]],
            "external": ext.most_common(15)}


def modules(conn, nb):
    """Módulos = pastas com ink-module.json / pastas filhas de 'modules/' / pastas de 1º nível com código."""
    rows = conn.execute("SELECT id, path, lang, doc FROM code_files WHERE notebook_id=?", (nb,)).fetchall()
    groups = defaultdict(list)
    manifest_dirs = {posixpath.dirname(r["path"]) for r in rows if r["path"].endswith("ink-module.json")}
    for r in rows:
        parts = r["path"].split("/")
        key = None
        for md in manifest_dirs:
            if md and r["path"].startswith(md + "/"):
                key = md if key is None or len(md) > len(key) else key
        if key is None and "modules" in parts[:-1]:
            i = parts.index("modules")
            key = "/".join(parts[:i + 2]) if len(parts) > i + 2 else None
        if key is None and len(parts) > 1:
            key = parts[0]
        groups[key or "(raiz)"].append(r)
    out = []
    for k, rs in sorted(groups.items()):
        ids = [r["id"] for r in rs]
        nsym = conn.execute(f"SELECT COUNT(*) FROM code_symbols WHERE file_id IN ({','.join('?' * len(ids))}) AND kind IN ('function','class','method')", ids).fetchone()[0]
        doc = next((r["doc"] for r in rs if r["doc"] and re.search(r"(readme|index|__init__)", r["path"], re.I)), "") or next((r["doc"] for r in rs if r["doc"]), "")
        out.append({"module": k, "files": len(rs), "symbols": nsym, "manifest": k in manifest_dirs, "doc": doc,
                    "langs": dict(Counter(r["lang"] for r in rs).most_common(4)),
                    "sample": [r["path"] for r in rs[:4]]})
    return out


def flows(conn, nb, max_depth=4, max_flows=8):
    """Cadeias a partir dos pontos de entrada, seguindo imports/chamadas resolvidos."""
    ov = overview(conn, nb)
    out = []
    for ep in ov["entry_points"][:max_flows]:
        f = conn.execute("SELECT id FROM code_files WHERE notebook_id=? AND path=?", (nb, ep["path"])).fetchone()
        if not f:
            continue
        seen, tree = {f["id"]}, []

        def walk(fid, d, label):
            if d > max_depth or len(tree) > 40:
                return
            for r in conn.execute("SELECT DISTINCT f.id, f.path, e.kind, e.target FROM code_edges e JOIN code_files f ON f.id=e.dst_id "
                                  "WHERE e.src_id=? ORDER BY e.kind, f.path LIMIT 8", (fid,)):
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                tree.append({"depth": d, "path": r["path"], "via": r["kind"] if r["kind"] != "calls" else f"chama {r['target']}()"})
                walk(r["id"], d + 1, r["path"])
        walk(f["id"], 1, ep["path"])
        if tree:
            out.append({"entry": ep["path"], "steps": tree})
    return out
