"""Registro de atividade real do aplicativo (mostrado na barra de status)."""
from . import db


def log(message: str, level: str = "info", notebook_id: int | None = None):
    try:
        with db.session() as conn:
            conn.execute("INSERT INTO activity(ts,level,message,notebook_id) VALUES(?,?,?,?)",
                         (db.now(), level, message, notebook_id))
            conn.execute("DELETE FROM activity WHERE id <= (SELECT MAX(id) FROM activity) - 500")
    except Exception:  # log nunca deve derrubar uma operação
        pass


def recent(limit: int = 60):
    with db.session() as conn:
        rows = conn.execute("SELECT * FROM activity ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
