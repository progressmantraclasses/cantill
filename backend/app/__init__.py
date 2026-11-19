import os
from datetime import date, datetime

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS


def create_app() -> Flask:
    from dotenv import load_dotenv
    load_dotenv()
    from . import models, seed
    from .api import chat, core, policy

    app = Flask(__name__, static_folder=None)
    app.json.default = lambda o: o.isoformat() if isinstance(o, (date, datetime)) else str(o)
    app.json.sort_keys = False
    CORS(app, origins=os.environ.get("CORS_ORIGINS", "*").split(","),
         allow_headers=["Content-Type", "X-User", "X-Role"], expose_headers=["Content-Disposition"])
    models.Base.metadata.create_all(models.engine)
    with app.app_context():
        seed.seed(models.Session)
    app.register_blueprint(core.bp)
    app.register_blueprint(policy.bp)
    app.register_blueprint(chat.bp)

    @app.teardown_appcontext
    def _cleanup(_exc):
        models.Session.remove()

    @app.errorhandler(404)
    def _nf(_e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(500)
    def _boom(e):
        models.Session.rollback()
        return jsonify({"error": "internal error", "detail": str(e.original_exception) if hasattr(e, "original_exception") else str(e)}), 500

    dist = os.environ.get("FRONTEND_DIST")
    if dist and os.path.isdir(dist):  # optional: serve the built UI from the same service
        @app.get("/", defaults={"path": ""})
        @app.get("/<path:path>")
        def spa(path):
            full = os.path.join(dist, path)
            return send_from_directory(dist, path if path and os.path.isfile(full) else "index.html")

    return app
