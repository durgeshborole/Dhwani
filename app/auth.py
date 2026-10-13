"""Authentication and role-based access control (dual login)."""
from __future__ import annotations

from functools import wraps

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from db import execute, fetchall, fetchone

auth_bp = Blueprint("auth", __name__)

USER_QUERY = """
SELECT u.user_id, u.username, u.full_name, u.email, u.home_line_id,
       r.role_name
FROM users u
JOIN roles r ON r.role_id = u.role_id
WHERE u.user_id = :uid
"""


# ---------------------------------------------------------------------
# Load the logged-in user before every request
# ---------------------------------------------------------------------
def load_logged_in_user() -> None:
    uid = session.get("user_id")
    g.user = None
    if uid is not None:
        try:
            g.user = fetchone(USER_QUERY, {"uid": uid})
        except Exception:
            g.user = None
            session.clear()
        if g.user is None:          # user was deleted
            session.clear()


# ---------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in first.", "error")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def role_required(role: str):
    """Only allow users whose role matches; others go back to their home."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Please log in first.", "error")
                return redirect(url_for("auth.login"))
            if g.user["role_name"] != role:
                flash("That page is for administrators only.", "error")
                return redirect(url_for("main.home"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


# ---------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        try:
            user = fetchone("SELECT * FROM users WHERE username = :u", {"u": username})
        except Exception:
            flash("Database is not initialized yet. Please create the schema first.", "error")
            return render_template("login.html")

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["user_id"]
            return redirect(url_for("main.home"))
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "ok")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    try:
        lines = fetchall("SELECT line_id, line_name FROM `lines` ORDER BY line_id")
    except Exception:
        lines = []
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip() or None
        password = request.form.get("password") or ""
        home_line = request.form.get("home_line_id") or None

        if not username or not full_name or not password:
            flash("Username, full name and password are required.", "error")
        elif fetchone("SELECT 1 FROM users WHERE username = :u", {"u": username}):
            flash("That username is already taken.", "error")
        else:
            execute(
                """INSERT INTO users
                       (username, password_hash, full_name, email, role_id, home_line_id)
                   VALUES (:u, :p, :f, :e, 2, :h)""",
                {"u": username,
                 "p": generate_password_hash(password),
                 "f": full_name,
                 "e": email,
                 "h": int(home_line) if home_line else None},
            )
            flash("Account created — please log in.", "ok")
            return redirect(url_for("auth.login"))
    return render_template("register.html", lines=lines)
