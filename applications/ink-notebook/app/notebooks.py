"""Lógica dos cadernos."""
import re
import shutil

from . import activity, config, db
from .errors import ApiError
from .text import fold


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-")
    return s[:50] or "caderno"


def _clean_name(name) -> str:
    name = (name or "").strip()
    if not name:
        raise ApiError("O nome do caderno não pode ficar vazio.")
    if len(name) > 80:
        raise ApiError("O nome do caderno pode ter no máximo 80 caracteres.")
    return name


def _dup_check(conn, name, ignore_id=None):
    for r in conn.execute("SELECT id, name FROM notebooks"):
        if r["id"] != ignore_id and r["name"].casefold() == name.casefold():
            raise ApiError(f"Já existe um caderno chamado “{r['name']}”.")


def get(conn, nb_id: int):
    row = conn.execute("SELECT * FROM notebooks WHERE id=?", (nb_id,)).fetchone()
    if not row:
        raise ApiError("Caderno não encontrado.", 404)
    return row


def list_all(conn):
    rows = conn.execute("""SELECT n.*, COUNT(d.id) AS doc_count, COALESCE(SUM(d.size),0) AS total_size
                           FROM notebooks n LEFT JOIN documents d ON d.notebook_id=n.id
                           GROUP BY n.id ORDER BY n.created_at DESC, n.id DESC""").fetchall()
    return [dict(r) for r in rows]


def create(name):
    name = _clean_name(name)
    with db.session() as conn:
        _dup_check(conn, name)
        base, slug, i = _slugify(name), None, 1
        slug = base
        while conn.execute("SELECT 1 FROM notebooks WHERE slug=?", (slug,)).fetchone() or \
                (config.NOTEBOOKS_DIR / slug).exists():
            i += 1
            slug = f"{base}-{i}"
        config.sources_dir(slug).mkdir(parents=True, exist_ok=True)
        cur = conn.execute("INSERT INTO notebooks(name,slug,created_at) VALUES(?,?,?)", (name, slug, db.now()))
        nb_id = cur.lastrowid
    activity.log(f"Caderno criado: {name}", notebook_id=nb_id)
    return nb_id


def rename(nb_id, name):
    name = _clean_name(name)
    with db.session() as conn:
        get(conn, nb_id)
        _dup_check(conn, name, nb_id)
        conn.execute("UPDATE notebooks SET name=? WHERE id=?", (name, nb_id))
    activity.log(f"Caderno renomeado para: {name}", notebook_id=nb_id)


def delete(nb_id):
    from . import indexer
    with indexer.LOCK:
        with db.session() as conn:
            nb = get(conn, nb_id)
            from .code import index as code_index
            code_index.purge(conn, nb_id)
            conn.execute("DELETE FROM notebooks WHERE id=?", (nb_id,))  # cascata: docs, trechos, índice
        shutil.rmtree(config.NOTEBOOKS_DIR / nb["slug"], ignore_errors=True)
    activity.log(f"Caderno excluído: {nb['name']}")
