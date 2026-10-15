import json

from flask import Flask, Response, jsonify, request

from . import config, db
from .api import bp
from .errors import ApiError


def create_app():
    config.ensure_dirs()
    db.init_db()
    app = Flask(__name__, static_folder=str(config.FRONTEND_DIR), static_url_path="")
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024
    app.register_blueprint(bp, url_prefix="/api")
    from .code_api import bp as code_bp
    app.register_blueprint(code_bp, url_prefix="/api/code")

    @app.get("/")
    def index():
        document = (config.FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
        document = document.replace("__WORKSPACE_CORE_ORIGIN_VALUE__", config.workspace_core_origin())
        return Response(document, mimetype="text/html")

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="Ink Notebook")

    @app.errorhandler(ApiError)
    def api_error(e):
        return jsonify(error=e.message), e.status

    @app.errorhandler(Exception)
    def unexpected(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            if request.path.startswith("/api"):
                return jsonify(error=e.description), e.code
            return e
        app.logger.exception("Erro inesperado")
        return jsonify(error=f"Erro interno: {e}"), 500

    return app
