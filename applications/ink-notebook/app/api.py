"""Rotas HTTP (JSON). A lógica fica nos outros módulos."""
from flask import Blueprint, jsonify, request

from . import activity, config, db, documents, notebooks, rag, search
from .errors import ApiError
from .extractors import SPECIAL_NAMES, TEXT_EXTS

bp = Blueprint("api", __name__)


@bp.get("/notebooks")
def list_notebooks():
    with db.session() as conn:
        return jsonify(notebooks.list_all(conn))


@bp.post("/notebooks")
def create_notebook():
    nb_id = notebooks.create((request.get_json(silent=True) or {}).get("name"))
    return jsonify(id=nb_id), 201


@bp.get("/notebooks/<int:nb_id>")
def get_notebook(nb_id):
    with db.session() as conn:
        nb = dict(notebooks.get(conn, nb_id))
        return jsonify(notebook=nb, documents=documents.list_for(conn, nb_id))


@bp.patch("/notebooks/<int:nb_id>")
def rename_notebook(nb_id):
    notebooks.rename(nb_id, (request.get_json(silent=True) or {}).get("name"))
    return jsonify(ok=True)


@bp.delete("/notebooks/<int:nb_id>")
def delete_notebook(nb_id):
    notebooks.delete(nb_id)
    return jsonify(ok=True)


@bp.post("/notebooks/<int:nb_id>/documents")
def upload(nb_id):
    files = request.files.getlist("files")
    if not files:
        raise ApiError("Nenhum arquivo recebido.")
    return jsonify(results=documents.add_uploads(nb_id, files))


@bp.delete("/documents/<int:doc_id>")
def delete_document(doc_id):
    documents.remove(doc_id)
    return jsonify(ok=True)


@bp.get("/documents/<int:doc_id>/content")
def document_content(doc_id):
    return jsonify(documents.preview(doc_id))


@bp.get("/notebooks/<int:nb_id>/search")
def do_search(nb_id):
    q = (request.args.get("q") or "").strip()
    with db.session() as conn:
        nb = notebooks.get(conn, nb_id)
        result = search.search(conn, nb, q)
    result["generation"] = rag.answer(q, result["hits"])
    for h in result["hits"]:
        h.pop("text", None)
    if q:
        activity.log(f"Busca concluída em “{nb['name']}”: {len(result['hits'])} resultado(s) para “{q[:60]}”"
                     f" ({result.get('took_ms', 0)} ms)", notebook_id=nb_id)
    return jsonify(result)


@bp.post("/notebooks/<int:nb_id>/reindex")
def reindex_nb(nb_id):
    return jsonify(documents=documents.reindex_notebook(nb_id))


@bp.post("/reindex")
def reindex_all():
    return jsonify(documents=documents.reindex_all())


@bp.get("/activity")
def get_activity():
    return jsonify(activity.recent(int(request.args.get("limit", 60))))


@bp.get("/settings")
def settings():
    with db.session() as conn:
        one = lambda sql: conn.execute(sql).fetchone()[0]
        stats = {
            "notebooks": one("SELECT COUNT(*) FROM notebooks"),
            "documents": one("SELECT COUNT(*) FROM documents"),
            "indexed": one("SELECT COUNT(*) FROM documents WHERE status='indexado'"),
            "errors": one("SELECT COUNT(*) FROM documents WHERE status IN ('erro','ausente')"),
            "pending": one("SELECT COUNT(*) FROM documents WHERE status='indexando'"),
            "chunks": one("SELECT COUNT(*) FROM chunks"),
            "terms": one("SELECT COUNT(DISTINCT term) FROM postings"),
            "postings": one("SELECT COUNT(*) FROM postings"),
        }
        sources_size = one("SELECT COALESCE(SUM(size),0) FROM documents")
    db_size = config.DB_PATH.stat().st_size if config.DB_PATH.exists() else 0
    return jsonify(
        data_dir=str(config.DATA_DIR), sources_pattern=str(config.NOTEBOOKS_DIR / "<caderno>" / "sources"),
        db_path=str(config.DB_PATH), db_size=db_size, sources_size=sources_size, stats=stats,
        index_method="BM25 local (SQLite) com expansão de prefixo e bônus de frase",
        llm={"enabled": rag.get_provider() is not None, "note": "Nenhum modelo generativo conectado ainda."},
        extensions=sorted(TEXT_EXTS | {".pdf"}), max_file_mb=config.MAX_FILE_MB)
