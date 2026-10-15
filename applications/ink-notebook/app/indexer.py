"""Indexação: texto -> trechos -> termos (índice invertido no SQLite).

Roda em uma thread de fundo (uma por vez) para a interface nunca travar.
"""
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from . import activity, config, db
from .chunker import chunk_lines
from .extractors import ExtractError, extract_text
from .text import tokenize

LOCK = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="indexer")


def submit(doc_id: int):
    _pool.submit(_safe_index, doc_id)


def _safe_index(doc_id: int):
    try:
        index_document(doc_id)
    except Exception as e:  # nada aqui pode derrubar o servidor
        _mark(doc_id, "erro", f"falha inesperada na indexação: {e}")
        activity.log(f"Falha ao indexar (id {doc_id}): {e}", "error")


def _mark(doc_id, status, error=None):
    with db.session() as conn:
        conn.execute("UPDATE documents SET status=?, error=? WHERE id=?", (status, error, doc_id))


def index_document(doc_id: int):
    with LOCK:
        with db.session() as conn:
            doc = conn.execute("SELECT d.*, n.slug FROM documents d JOIN notebooks n ON n.id=d.notebook_id "
                               "WHERE d.id=?", (doc_id,)).fetchone()
        if not doc:
            return
        name, nb = doc["filename"], doc["notebook_id"]
        path = config.source_path(doc["slug"], name)
        activity.log(f"Indexando: {name}", notebook_id=nb)

        if not path.exists():
            with db.session() as conn:
                conn.execute("DELETE FROM chunks WHERE document_id=?", (doc_id,))
                conn.execute("UPDATE documents SET status='ausente', error=?, chunk_count=0 WHERE id=?",
                             ("arquivo original não encontrado na pasta de fontes", doc_id))
            activity.log(f"Arquivo ausente: {name}", "warn", nb)
            return

        try:
            text = extract_text(path)
            lines = text.splitlines()
            chunks = chunk_lines(lines, doc["ext"])
        except ExtractError as e:
            with db.session() as conn:
                conn.execute("DELETE FROM chunks WHERE document_id=?", (doc_id,))
                conn.execute("UPDATE documents SET status='erro', error=?, chunk_count=0 WHERE id=?",
                             (str(e), doc_id))
            activity.log(f"Não foi possível indexar {name}: {e}", "error", nb)
            return

        with db.session() as conn:
            conn.execute("DELETE FROM chunks WHERE document_id=?", (doc_id,))  # postings caem em cascata
            for i, c in enumerate(chunks):
                toks = tokenize(c["text"] + " " + c["heading"])
                cur = conn.execute(
                    "INSERT INTO chunks(document_id,notebook_id,idx,start_line,end_line,heading,text,length) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (doc_id, nb, i, c["start_line"], c["end_line"], c["heading"], c["text"], max(len(toks), 1)))
                conn.executemany("INSERT INTO postings(term,chunk_id,notebook_id,tf) VALUES(?,?,?,?)",
                                 [(t, cur.lastrowid, nb, tf) for t, tf in Counter(toks).items()])
            conn.execute("UPDATE documents SET status='indexado', error=NULL, lines=?, chunk_count=?, size=?, "
                         "indexed_at=? WHERE id=?",
                         (len(lines), len(chunks), path.stat().st_size, db.now(), doc_id))
        activity.log(f"Índice atualizado: {name} ({len(chunks)} trechos)", notebook_id=nb)
