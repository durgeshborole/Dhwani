"""Central configuration, read from environment variables (.env supported)."""
from __future__ import annotations

import os
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:      # dotenv is optional
    pass


class Config:
    # ---- MySQL connection ------------------------------------------------
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "dhwani")

    # ---- Flask -----------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # ---- Mumbai coordinates (used by the weather ETL) --------------------
    MUMBAI_LAT = float(os.getenv("MUMBAI_LAT", "19.0760"))
    MUMBAI_LON = float(os.getenv("MUMBAI_LON", "72.8777"))

    # ---- Optional live-data API keys ------------------------------------
    TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "")   # traffic (free tier)
    SAFAR_API_KEY = os.getenv("SAFAR_API_KEY", "")     # air quality (optional)

    # ---------------------------------------------------------------------
    @classmethod
    def db_url(cls) -> str:
        """SQLAlchemy connection URL (PyMySQL driver)."""
        return (
            f"mysql+pymysql://{quote_plus(cls.DB_USER)}:{quote_plus(cls.DB_PASSWORD)}"
            f"@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}?charset=utf8mb4"
        )


if __name__ == "__main__":
    print("DB URL:", Config.db_url().replace(Config.DB_PASSWORD or "x", "***"))
