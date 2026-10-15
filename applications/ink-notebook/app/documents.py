"""Lógica dos documentos: adicionar, remover, prévia e reconstrução do índice."""
import re

from . import activity, config, db, indexer, notebooks
from .errors import ApiError
from .extractors import ExtractError, extract_text, file_ext, unsupported_reason

_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _clean_filename(name: str) -> str:
    name = _BAD.sub("_", (name or "").replace("\\", "/").split("/")[-1]).strip(" .")
    return name[:150]


def _unique_path(folder, name):
    p = folder / name
    if not p.exists():
        return p
    stem, ext, i = p.stem, p.suffix, 2
    while (folder / f"{stem} ({i}){ext}").exists():
        i += 1
    return folder / f"{stem} ({i}){ext}"


def _register(conn, nb_id, path):
    st = path.stat()
    cur = conn.execute("INSERT INTO documents(notebook_id,filename,ext,size,added_at,status) "
                       "VALUES(?,?,?,?,?,'indexando')", (nb_id, path.name, file_ext(path.name), st.st_size, db.now()))
    return cur.lastrowid


def list_for(conn, nb_id):
    rows = conn.execute("SELECT * FROM documents WHERE notebook_id=? ORDER BY added_at DESC, id DESC",
                        (nb_id,)).fetchall()
    return [dict(r) for r in rows]


def get(conn, doc_id):
    row = conn.execute("SELECT d.*, n.slug, n.name AS notebook_name FROM documents d "
                       "JOIN notebooks n ON n.id=d.notebook_id WHERE d.id=?", (doc_id,)).fetchone()
    if not row:
        raise ApiError("Documento não encontrado.", 404)
    return row


def add_uploads(nb_id, files):
    """Salva cada arquivo em data/notebooks/<caderno>/sources/ e agenda a indexação."""
    results, new_ids, logs = [], [], []  # logs só depois do commit (evita lock do SQLite)
    with db.session() as conn:
        nb = notebooks.get(conn, nb_id)
        folder = config.sources_dir(nb["slug"])
        folder.mkdir(parents=True, exist_ok=True)
        for fs in files:
            name = _clean_filename(fs.filename)
            if not name:
                continue
            reason = unsupported_reason(name)
            if reason:
                results.append({"name": name, "ok": False, "error": reason})
                logs.append((f"Arquivo recusado ({name}): {reason}", "warn"))
                continue
            path = _unique_path(folder, name)
            try:
                fs.save(path)
                if path.stat().st_size > config.MAX_FILE_MB * 1024 * 1024:
                    path.unlink(missing_ok=True)
                    raise ValueError(f"arquivo maior que {config.MAX_FILE_MB} MB")
                doc_id = _register(conn, nb_id, path)
            except Exception as e:
                path.unlink(missing_ok=True)
                results.append({"name": name, "ok": False, "error": f"falha ao salvar: {e}"})
                logs.append((f"Falha ao adicionar {name}: {e}", "error"))
                continue
            new_ids.append(doc_id)
            results.append({"name": path.name, "ok": True, "id": doc_id})
            logs.append((f"Documento adicionado: {path.name}", "info"))
    for msg, level in logs:
        activity.log(msg, level, nb_id)
    for i in new_ids:  # só depois do commit
        indexer.submit(i)
    return results


def remove(doc_id):
    with indexer.LOCK:
        with db.session() as conn:
            doc = get(conn, doc_id)
            conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
        try:
            config.source_path(doc["slug"], doc["filename"]).unlink(missing_ok=True)
        except OSError as e:
            activity.log(f"Índice limpo, mas não consegui apagar o arquivo {doc['filename']}: {e}", "warn")
    activity.log(f"Documento removido: {doc['filename']}", notebook_id=doc["notebook_id"])


def preview(doc_id):
    with db.session() as conn:
        doc = get(conn, doc_id)
    path = config.source_path(doc["slug"], doc["filename"])
    if not path.exists():
        raise ApiError("O arquivo original não está mais na pasta de fontes.", 404)
    try:
        lines = extract_text(path).splitlines()
    except ExtractError as e:
        raise ApiError(f"Não foi possível abrir a prévia: {e}", 422)
    truncated = len(lines) > config.MAX_PREVIEW_LINES
    d = {k: doc[k] for k in ("id", "notebook_id", "filename", "ext", "size", "lines", "status", "added_at")}
    return {"document": d, "lines": lines[:config.MAX_PREVIEW_LINES], "truncated": truncated, "total_lines": len(lines)}


def reindex_notebook(nb_id):
    """Relê os arquivos da pasta: pega alterações externas e arquivos novos colocados lá."""
    with db.session() as conn:
        nb = notebooks.get(conn, nb_id)
        folder = config.sources_dir(nb["slug"])
        known = {r["filename"] for r in conn.execute("SELECT filename FROM documents WHERE notebook_id=?", (nb_id,))}
        found = 0
        if folder.exists():
            for p in sorted(folder.iterdir()):
                if p.is_file() and p.name not in known and unsupported_reason(p.name) is None:
                    _register(conn, nb_id, p)
                    found += 1
        conn.execute("UPDATE documents SET status='indexando' WHERE notebook_id=?", (nb_id,))
        ids = [r["id"] for r in conn.execute("SELECT id FROM documents WHERE notebook_id=?", (nb_id,))]
    extra = f" ({found} arquivo(s) novo(s) encontrado(s) na pasta)" if found else ""
    activity.log(f"Reconstruindo índice de “{nb['name']}”: {len(ids)} documento(s){extra}", notebook_id=nb_id)
    for i in ids:
        indexer.submit(i)
    return len(ids)


def reindex_all():
    with db.session() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM notebooks")]
    return sum(reindex_notebook(i) for i in ids)
