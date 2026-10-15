"""Indexação de código: grava arquivos, símbolos, referências, trechos (FTS) e resolve relações entre arquivos."""
import hashlib
import io
import json
import posixpath
import zipfile
from collections import defaultdict

from .. import db
from ..chunker import chunk_lines
from ..extractors import ExtractError, _decode
from ..text import tokenize
from . import parsers, rules

RES_EXTS = (".js", ".mjs", ".ts", ".tsx", ".jsx", ".json", ".css", ".py", ".html", ".php", ".md")
ZIP_MAX_TOTAL = 600 * 1024 * 1024


def purge(conn, nb):
    """Remove TUDO do índice de código de um caderno (inclui as linhas do FTS, que não têm cascata)."""
    if db.has_fts(conn):
        conn.execute("DELETE FROM code_fts WHERE rowid IN (SELECT id FROM code_chunks WHERE notebook_id=?)", (nb,))
    for t in ("code_edges", "code_refs", "code_symbols", "code_chunks", "code_files", "code_history"):
        conn.execute(f"DELETE FROM {t} WHERE notebook_id=?", (nb,))


def _drop_file_index(conn, fid):
    if db.has_fts(conn):
        conn.execute("DELETE FROM code_fts WHERE rowid IN (SELECT id FROM code_chunks WHERE file_id=?)", (fid,))
    for t in ("code_symbols", "code_refs", "code_chunks"):
        conn.execute(f"DELETE FROM {t} WHERE file_id=?", (fid,))
    conn.execute("DELETE FROM code_edges WHERE src_id=?", (fid,))


def remove_file(conn, nb, path):
    row = conn.execute("SELECT id FROM code_files WHERE notebook_id=? AND path=?", (nb, path)).fetchone()
    if row:
        _drop_file_index(conn, row["id"])
        conn.execute("DELETE FROM code_files WHERE id=?", (row["id"],))
    return bool(row)


def index_file(conn, nb, path, raw: bytes):
    """Indexa um arquivo. Devolve {'path', 'status': novo|atualizado|inalterado|ignorado|erro, ...}."""
    path = rules.norm_path(path)
    if not path:
        return {"path": path, "status": "ignorado", "reason": "caminho vazio"}
    reason = rules.ignore_reason(path, len(raw))
    if reason:
        return {"path": path, "status": "ignorado", "reason": reason}
    lang, ext = rules.language_of(path)
    secret = rules.is_secret_file(path)
    digest = hashlib.sha1(raw).hexdigest()
    old = conn.execute("SELECT id, hash, status FROM code_files WHERE notebook_id=? AND path=?", (nb, path)).fetchone()
    if old and old["hash"] == digest and old["status"] != "erro":
        return {"path": path, "status": "inalterado", "lang": lang}
    try:
        text = "" if secret else _decode(raw)
    except ExtractError as e:
        return {"path": path, "status": "ignorado", "reason": str(e)}
    if old:
        _drop_file_index(conn, old["id"])
        conn.execute("DELETE FROM code_files WHERE id=?", (old["id"],))
    err, info = None, parsers.new()
    secret_lines = [] if secret else rules.find_secret_lines(text)
    if not secret:
        try:
            info = parsers.parse(lang, text, path)
        except Exception as e:  # um parser com bug não pode derrubar a importação
            err = f"análise estrutural falhou ({type(e).__name__}: {e}); o texto continua pesquisável"
    lines = text.splitlines()
    cur = conn.execute(
        "INSERT INTO code_files(notebook_id,path,name,ext,lang,size,lines,hash,text,doc,exports,entry,secret,secret_lines,"
        "status,error,indexed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (nb, path, path.rsplit("/", 1)[-1], ext, lang, len(raw), len(lines), digest, text, info["doc"],
         json.dumps(info["exports"][:80]), int(info["entry"]), int(secret), json.dumps(secret_lines[:50]),
         "sensivel" if secret else ("erro" if err else "indexado"), err, db.now()))
    fid = cur.lastrowid
    conn.executemany("INSERT INTO code_symbols(file_id,notebook_id,name,kind,parent,line,end_line,sig) VALUES(?,?,?,?,?,?,?,?)",
                     [(fid, nb, s["name"], s["kind"], s["parent"], s["line"], s["end"], s["sig"]) for s in info["symbols"]])
    refs = {(n, l, "call") for n, l in info["calls"]} | {(n, l, k) for n, l, k in info["refs"]}
    conn.executemany("INSERT INTO code_refs(file_id,notebook_id,name,line,kind) VALUES(?,?,?,?,?)",
                     [(fid, nb, n, l, k) for n, l, k in sorted(refs)])
    # arestas "cruas" (sem destino); resolve() preenche dst_id depois
    conn.executemany("INSERT INTO code_edges(notebook_id,src_id,dst_id,kind,target,line) VALUES(?,?,NULL,?,?,?)",
                     [(nb, fid, "imports" if im["kind"] != "ref" else "references",
                       ("?" if im["optional"] else "") + im["spec"], im["line"]) for im in info["imports"]])
    if not secret and db.has_fts(conn):
        for c in chunk_lines(lines, ext):
            cc = conn.execute("INSERT INTO code_chunks(file_id,notebook_id,start_line,end_line,heading,text) VALUES(?,?,?,?,?,?)",
                              (fid, nb, c["start_line"], c["end_line"], c["heading"], c["text"]))
            toks = tokenize(c["text"] + " " + c["heading"] + " " + path)
            conn.execute("INSERT INTO code_fts(rowid,tokens) VALUES(?,?)", (cc.lastrowid, " ".join(toks)))
    elif not secret:
        for c in chunk_lines(lines, ext):
            conn.execute("INSERT INTO code_chunks(file_id,notebook_id,start_line,end_line,heading,text) VALUES(?,?,?,?,?,?)",
                         (fid, nb, c["start_line"], c["end_line"], c["heading"], c["text"]))
    return {"path": path, "status": "atualizado" if old else "novo", "lang": lang, "error": err,
            "secret": bool(secret or secret_lines)}


def expand_zip(data: bytes):
    """Gera (caminho, bytes) para cada entrada útil do ZIP (remove a pasta raiz comum)."""
    zf = zipfile.ZipFile(io.BytesIO(data))
    infos = [i for i in zf.infolist() if not i.is_dir()]
    if sum(i.file_size for i in infos) > ZIP_MAX_TOTAL:
        raise ValueError("ZIP descompactado grande demais (>600 MB)")
    names = [rules.norm_path(i.filename) for i in infos]
    roots = {n.split("/")[0] for n in names if n}
    strip = len(roots) == 1 and all("/" in n for n in names)
    for i, n in zip(infos, names):
        if not n:
            continue
        p = n.split("/", 1)[1] if strip else n
        if i.file_size > rules.MAX_BYTES or rules.ignore_reason(p, i.file_size):
            yield p, None, i.file_size
        else:
            yield p, zf.read(i), i.file_size


# ------------------------------------------------------------------ resolução
def _candidates(base):
    yield base
    for e in RES_EXTS:
        yield base + e
    for e in RES_EXTS:
        yield base + "/index" + e
    yield base + "/__init__.py"


def _resolve(src, spec, lang, paths, suffix):
    spec = spec.split("#")[0]
    if not spec:
        return None
    sdir = posixpath.dirname(src)
    if lang == "python":
        level = len(spec) - len(spec.lstrip("."))
        mod = spec.lstrip(".").replace(".", "/")
        roots = []
        if level:
            d = sdir
            for _ in range(level - 1):
                d = posixpath.dirname(d)
            roots = [d]
        else:
            d = sdir
            while True:
                roots.append(d)
                if not d:
                    break
                d = posixpath.dirname(d)
        for r in roots:
            base = posixpath.normpath(posixpath.join(r, mod)) if mod else r
            if mod:
                for c in (base + ".py", base + "/__init__.py"):
                    if c in paths:
                        return c
            elif level and (base + "/__init__.py") in paths:
                return base + "/__init__.py"
        return None
    if lang == "php" and "\\" in spec:
        tail = spec.replace("\\", "/") + ".php"
        hits = suffix.get(tail.lower())
        return hits[0] if hits and len(hits) == 1 else None
    rel = spec.startswith(".")
    bases = [posixpath.normpath(posixpath.join(sdir, spec))] if rel else []
    if not rel and spec.startswith("/"):
        bases += [spec.lstrip("/")]
        bases += [posixpath.normpath(posixpath.join(sdir, spec.lstrip("/")))]
    elif not rel and "/" in spec and not spec.startswith("@"):
        bases += [posixpath.normpath(posixpath.join(sdir, spec)), spec]
    for b in bases:
        for c in _candidates(b.strip("/")):
            if c in paths:
                return c
    # último recurso: sufixo único (ex.: HTML pede /app.js e o arquivo está em frontend/app.js)
    if rel or spec.startswith("/") or "/" in spec or "." in spec.rsplit("/", 1)[-1]:
        tail = posixpath.normpath(spec.lstrip("./").lstrip("/")).lower()
        hits = suffix.get(tail)
        if hits and len(hits) == 1:
            return hits[0]
    return None


def resolve(conn, nb):
    """Recalcula as arestas do projeto: imports/referências resolvidos + chamadas entre arquivos."""
    files = conn.execute("SELECT id, path, lang FROM code_files WHERE notebook_id=?", (nb,)).fetchall()
    by_path = {f["path"]: f for f in files}
    paths = set(by_path)
    suffix = defaultdict(list)
    for p in paths:
        parts = p.split("/")
        for i in range(len(parts)):
            suffix["/".join(parts[i:]).lower()].append(p)
    conn.execute("DELETE FROM code_edges WHERE notebook_id=? AND kind='calls'", (nb,))
    edges = conn.execute("SELECT id, src_id, target, kind FROM code_edges WHERE notebook_id=? AND kind!='calls'", (nb,)).fetchall()
    fid_path = {f["id"]: f for f in files}
    upd, drop, imported = [], [], defaultdict(set)
    for e in edges:
        src = fid_path.get(e["src_id"])
        if not src:
            continue
        spec = e["target"]
        optional = spec.startswith("?")
        spec = spec.lstrip("?")
        dst = _resolve(src["path"], spec, src["lang"], paths, suffix)
        if dst is None and src["lang"] in ("json",) and e["kind"] == "references":  # relativo à raiz do projeto
            dst = _resolve("", spec, "javascript", paths, suffix)
        if dst is None and optional:
            drop.append((e["id"],))
        else:
            upd.append((by_path[dst]["id"] if dst else None, spec, e["id"]))
            if dst:
                imported[src["id"]].add(by_path[dst]["id"])
    conn.executemany("DELETE FROM code_edges WHERE id=?", drop)
    conn.executemany("UPDATE code_edges SET dst_id=?, target=? WHERE id=?", upd)
    # chamadas entre arquivos
    defs = defaultdict(set)
    for r in conn.execute("SELECT name, file_id FROM code_symbols WHERE notebook_id=? AND kind IN ('function','class','method')", (nb,)):
        defs[r["name"]].add(r["file_id"])
    seen, new_edges = set(), []
    for r in conn.execute("SELECT file_id, name, MIN(line) AS line FROM code_refs WHERE notebook_id=? AND kind='call' GROUP BY file_id, name", (nb,)):
        cands = defs.get(r["name"])
        if not cands:
            continue
        pick = [c for c in cands if c in imported[r["file_id"]]]
        if not pick and len(cands) == 1 and len(r["name"]) >= 4:
            pick = list(cands)
        for d in pick:
            if d != r["file_id"] and (r["file_id"], d, r["name"]) not in seen:
                seen.add((r["file_id"], d, r["name"]))
                new_edges.append((nb, r["file_id"], d, "calls", r["name"], r["line"]))
    conn.executemany("INSERT INTO code_edges(notebook_id,src_id,dst_id,kind,target,line) VALUES(?,?,?,?,?,?)", new_edges)
    return {"imports": len(upd), "calls": len(new_edges)}
