"""Flask application factory for Dhwani."""
from __future__ import annotations

from flask import Flask

from config import Config
from db import ensure_schema


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=Config.SECRET_KEY,
        JSON_SORT_KEYS=False,
    )

    try:
        ensure_schema()
    except Exception:
        pass

    from app.auth import auth_bp, load_logged_in_user
    from app.routes import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.before_request(load_logged_in_user)

    return app
