"""Flask application factory."""
import os
from datetime import date, datetime

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from . import database, models, seed
from .api import chat, core, policy, requests

MAX_UPLOAD_MB = 20


def create_app() -> Flask:
    app = Flask(__name__, static_folder=None)
    app.json.default = lambda o: o.isoformat() if isinstance(o, (date, datetime)) else str(o)
    app.json.sort_keys = False
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

    _configure_cors(app)
    _init_database()
    for blueprint in (core.bp, policy.bp, chat.bp, requests.bp):
        app.register_blueprint(blueprint)
    _register_handlers(app)
    _serve_frontend(app, os.environ.get("FRONTEND_DIST"))
    return app


def _configure_cors(app: Flask) -> None:
    origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
    CORS(app, origins=origins or "*", allow_headers=["Content-Type", "X-User", "X-Role"],
         expose_headers=["Content-Disposition"])


def _init_database() -> None:
    """Create missing tables and load the kit data on first start."""
    database.create_schema(models.Base.metadata)
    try:
        seed.seed(database.Session)
    finally:
        database.Session.remove()


def _register_handlers(app: Flask) -> None:
    @app.teardown_appcontext
    def _cleanup(_exc):
        database.Session.remove()

    @app.errorhandler(HTTPException)
    def _http_error(e: HTTPException):
        messages = {400: "The request could not be read (check that the body is valid JSON).",
                    404: "not found", 405: "method not allowed",
                    413: f"The file is too large. The limit is {MAX_UPLOAD_MB} MB."}
        return jsonify({"error": messages.get(e.code, e.description)}), e.code

    @app.errorhandler(500)
    def _server_error(e):
        database.Session.rollback()
        detail = getattr(e, "original_exception", None) or e
        return jsonify({"error": "internal error", "detail": str(detail)}), 500


def _serve_frontend(app: Flask, dist: str | None) -> None:
    """Optional: serve the built UI from the same service."""
    if not dist or not os.path.isdir(dist):
        return

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def spa(path):
        is_file = path and os.path.isfile(os.path.join(dist, path))
        return send_from_directory(dist, path if is_file else "index.html")
