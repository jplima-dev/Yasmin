"""Rotas HTTP do Code Notebook (/api/code/...). Aditivo: não altera nenhuma rota existente."""
import json

from flask import Blueprint, jsonify, request

from . import activity, db, notebooks
from .code import ai, docs, index, qa, query, rules
from .errors import ApiError

bp = Blueprint("code_api", __name__)


def _nb(conn, nb_id):
    return notebooks.get(conn, nb_id)


@bp.get("/rules")
def get_rules():
    return jsonify(ignore_dirs=sorted(rules.IGNORE_DIRS), ignore_ext=sorted(rules.IGNORE_EXT),
                   ignore_names=sorted(rules.IGNORE_NAMES), max_bytes=rules.MAX_BYTES,
                   known_ext=sorted(rules.LANG))


@bp.post("/<int:nb_id>/import")
def import_files(nb_id):
    files = request.files.getlist("files")
    paths = request.form.getlist("paths")
    if not files:
        raise ApiError("Nenhum arquivo recebido.")
    if len(paths) != len(files):
        paths = [f.filename for f in files]
    summary = {"new": 0, "updated": 0, "unchanged": 0, "ignored": {}, "errors": [], "languages": {}, "secrets": []}

    def tally(r):
        st = r["status"]
        if st == "ignorado":
            summary["ignored"][r["reason"]] = summary["ignored"].get(r["reason"], 0) + 1
            return
        summary[{"novo": "new", "atualizado": "updated", "inalterado": "unchanged"}.get(st, "new")] += 1
        summary["languages"][r.get("lang") or "?"] = summary["languages"].get(r.get("lang") or "?", 0) + 1
        if r.get("error"):
            summary["errors"].append(f"{r['path']}: {r['error']}")
        if r.get("secret"):
            summary["secrets"].append(r["path"])

    with db.session() as conn:
        _nb(conn, nb_id)
        for fs, p in zip(files, paths):
            try:
                if (fs.filename or "").lower().endswith(".zip") and not request.form.get("as_file"):
                    for zp, data, size in index.expand_zip(fs.read()):
                        tally({"path": zp, "status": "ignorado", "reason": rules.ignore_reason(zp, size) or "arquivo grande demais (>1 MB)"}
                              if data is None else index.index_file(conn, nb_id, zp, data))
                else:
                    tally(index.index_file(conn, nb_id, p, fs.read()))
            except Exception as e:  # um arquivo ruim não derruba o lote
                summary["errors"].append(f"{p}: {e}")
    return jsonify(summary)


@bp.post("/<int:nb_id>/finalize")
def finalize(nb_id):
    with db.session() as conn:
        nb = _nb(conn, nb_id)
        rel = index.resolve(conn, nb_id)
        ov = query.overview(conn, nb_id)
    activity.log(f"Projeto de código indexado em “{nb['name']}”: {ov['files']} arquivos, {ov['symbols']} símbolos, {rel['imports']} imports, {rel['calls']} chamadas", notebook_id=nb_id)
    return jsonify(relations=rel, overview=ov)


@bp.get("/<int:nb_id>/overview")
def overview(nb_id):
    with db.session() as conn:
        nb = _nb(conn, nb_id)
        return jsonify(name=nb["name"], overview=query.overview(conn, nb_id), modules=query.modules(conn, nb_id), flows=query.flows(conn, nb_id))


@bp.get("/<int:nb_id>/tree")
def tree(nb_id):
    with db.session() as conn:
        _nb(conn, nb_id)
        rows = conn.execute("SELECT id, path, lang, lines, secret, status FROM code_files WHERE notebook_id=? ORDER BY path", (nb_id,)).fetchall()
        return jsonify(files=[dict(r) for r in rows])


@bp.get("/<int:nb_id>/file")
def file_view(nb_id):
    with db.session() as conn:
        _nb(conn, nb_id)
        f = query.get_file(conn, nb_id, request.args.get("path") or "")
        if not f:
            hits = query.find_files(conn, nb_id, request.args.get("path") or "")
            f = query.get_file(conn, nb_id, fid=hits[0]["id"]) if len(hits) == 1 else None
        if not f:
            raise ApiError("Arquivo não encontrado no índice.", 404)
        d = query.file_detail(conn, nb_id, f)
        d["content"] = f["text"].split("\n") if not f["secret"] else ["(arquivo sensível: conteúdo não armazenado)"]
        d["secret_lines"] = json.loads(f["secret_lines"])
        return jsonify(d)


@bp.get("/<int:nb_id>/search")
def search(nb_id):
    with db.session() as conn:
        _nb(conn, nb_id)
        return jsonify(query.search(conn, nb_id, (request.args.get("q") or "").strip()))


@bp.get("/<int:nb_id>/graph")
def graph(nb_id):
    a = request.args
    with db.session() as conn:
        _nb(conn, nb_id)
        root = None
        if a.get("path"):
            hits = query.find_files(conn, nb_id, a["path"])
            if not hits:
                raise ApiError("Arquivo não encontrado no índice.", 404)
            root = hits[0]["id"]
        kinds = [k for k in (a.get("kinds") or "imports,references,calls").split(",") if k in ("imports", "references", "calls")]
        return jsonify(query.graph(conn, nb_id, root, max(1, min(int(a.get("depth", 1)), 3)), a.get("dir", "both"), kinds or ("imports",)))


@bp.get("/<int:nb_id>/docs")
def generate_docs(nb_id):
    with db.session() as conn:
        nb = _nb(conn, nb_id)
        return jsonify(docs=docs.generate(conn, nb_id, nb["name"]))


@bp.post("/<int:nb_id>/ask")
def ask(nb_id):
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        raise ApiError("Escreva uma pergunta.")
    with db.session() as conn:
        _nb(conn, nb_id)
        if conn.execute("SELECT COUNT(*) FROM code_files WHERE notebook_id=?", (nb_id,)).fetchone()[0] == 0:
            return jsonify(mode="index", kind="empty", sources=[], links={}, text="O projeto ainda está vazio. Importe uma pasta, arquivos ou ZIP primeiro.")
        res = qa.ask(conn, nb_id, question, confirm=bool(body.get("confirm")))
        res["links"] = qa.make_links(conn, nb_id, res.get("text", ""))
        if res["mode"] != "needs_confirmation":
            qa.log_history(conn, nb_id, question, res)
    return jsonify(res)


@bp.get("/<int:nb_id>/history")
def history(nb_id):
    with db.session() as conn:
        _nb(conn, nb_id)
        rows = conn.execute("SELECT ts, question, mode, answer FROM code_history WHERE notebook_id=? ORDER BY id DESC LIMIT 40", (nb_id,)).fetchall()
        return jsonify(items=[{"ts": r["ts"], "question": r["question"], "mode": r["mode"], **json.loads(r["answer"])} for r in reversed(rows)])


@bp.delete("/<int:nb_id>/project")
def clear_project(nb_id):
    with db.session() as conn:
        _nb(conn, nb_id)
        index.purge(conn, nb_id)
    return jsonify(ok=True)


@bp.delete("/<int:nb_id>/file")
def delete_file(nb_id):
    with db.session() as conn:
        _nb(conn, nb_id)
        ok = index.remove_file(conn, nb_id, request.args.get("path") or "")
        index.resolve(conn, nb_id)
    return jsonify(ok=ok)


@bp.get("/settings")
def get_settings():
    with db.session() as conn:
        return jsonify(ai.public_settings(ai.load_settings(conn)))


@bp.post("/settings")
def set_settings():
    with db.session() as conn:
        ai.save_settings(conn, request.get_json(silent=True) or {})
        return jsonify(ai.public_settings(ai.load_settings(conn)))
