"""Database access layer — one SQLAlchemy engine, small helpers for queries.

All application code goes through these helpers, so the connection details
live in exactly one place (config.py).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
from sqlalchemy import create_engine, text

from config import Config

engine = create_engine(
    Config.db_url(),
    pool_pre_ping=True,      # reconnect if the server dropped the connection
    pool_recycle=3600,
    future=True,
)


# ---------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------
def query_df(sql: str, params: Mapping[str, Any] | None = None) -> pd.DataFrame:
    """Run a SELECT and return a pandas DataFrame."""
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=dict(params or {}))


def fetchall(sql: str, params: Mapping[str, Any] | None = None) -> list[Mapping[str, Any]]:
    """Run a SELECT and return a list of row mappings."""
    with engine.connect() as conn:
        return list(conn.execute(text(sql), dict(params or {})).mappings())


def fetchone(sql: str, params: Mapping[str, Any] | None = None) -> Mapping[str, Any] | None:
    rows = fetchall(sql, params)
    return rows[0] if rows else None


def scalar(sql: str, params: Mapping[str, Any] | None = None) -> Any:
    with engine.connect() as conn:
        return conn.execute(text(sql), dict(params or {})).scalar()


# ---------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------
def execute(sql: str, params: Mapping[str, Any] | None = None) -> int:
    """Run a single INSERT/UPDATE/DELETE. Returns affected row count."""
    with engine.begin() as conn:
        result = conn.execute(text(sql), dict(params or {}))
        return result.rowcount


def executemany(sql: str, rows: Iterable[Mapping[str, Any]]) -> int:
    """Run one statement for many parameter sets, in a single transaction."""
    rows = [dict(r) for r in rows]
    if not rows:
        return 0
    with engine.begin() as conn:
        conn.execute(text(sql), rows)
    return len(rows)


def table_exists(table_name: str) -> bool:
    """Return True if a table exists in the current database."""
    try:
        with engine.connect() as conn:
            stmt = text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = :table_name"
            )
            return bool(conn.execute(stmt, {"table_name": table_name}).scalar())
    except Exception:
        return False


def ensure_schema() -> bool:
    """Create the default Dhwani schema if the database is uninitialized."""
    if table_exists("lines"):
        return True

    mysql = shutil.which("mysql") or shutil.which("mysql.exe")
    if not mysql:
        return False

    project_root = Path(__file__).resolve().parent
    schema_sql = project_root / "database" / "schema.sql"
    seed_sql = project_root / "database" / "seed.sql"

    if not schema_sql.exists() or not seed_sql.exists():
        return False

    try:
        base_cmd = [
            mysql,
            "--host=" + Config.DB_HOST,
            "--port=" + str(Config.DB_PORT),
            "--user=" + Config.DB_USER,
            "--password=" + str(Config.DB_PASSWORD),
        ]
        with open(schema_sql, "r", encoding="utf-8") as f:
            subprocess.run(base_cmd, stdin=f, check=True)

        with open(seed_sql, "r", encoding="utf-8") as f:
            subprocess.run(base_cmd + ["--database=" + Config.DB_NAME], stdin=f, check=True)
        return table_exists("lines")
    except Exception:
        return False


def ping() -> bool:
    """True if the database is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


if __name__ == "__main__":
    ok = ping()
    print("Database reachable:", ok)
    if ok:
        print("Lines table exists:", table_exists("lines"))
        print("Trips:", scalar("SELECT COUNT(*) FROM trips"))
        print("Delay records:", scalar("SELECT COUNT(*) FROM delay_records"))
