"""Weather ETL — pulls real rainfall for Mumbai from Open-Meteo.

Open-Meteo needs no API key, which is why it is the project's live weather
source. Two endpoints are used:
  * archive  -> historical hourly data (fills the monsoon history)
  * forecast -> the current hour (drives the live risk score)
"""
from __future__ import annotations

import datetime as dt
from typing import Iterable

import requests

from config import Config
from db import execute, executemany

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CURRENT_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY = "precipitation,temperature_2m,relative_humidity_2m"

UPSERT = """
INSERT INTO weather_observations
    (observed_at, rainfall_mm, temp_c, humidity, source)
VALUES
    (:observed_at, :rainfall_mm, :temp_c, :humidity, :source)
ON DUPLICATE KEY UPDATE
    rainfall_mm = VALUES(rainfall_mm),
    temp_c      = VALUES(temp_c),
    humidity    = VALUES(humidity)
"""


def _rows_from_hourly(payload: dict, source: str) -> list[dict]:
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    rain = hourly.get("precipitation", [])
    temp = hourly.get("temperature_2m", [])
    hum = hourly.get("relative_humidity_2m", [])
    rows = []
    for i, t in enumerate(times):
        rows.append({
            "observed_at": t.replace("T", " "),
            "rainfall_mm": float(rain[i] or 0) if i < len(rain) else 0.0,
            "temp_c": float(temp[i]) if i < len(temp) and temp[i] is not None else None,
            "humidity": int(hum[i]) if i < len(hum) and hum[i] is not None else None,
            "source": source,
        })
    return rows


def fetch_archive(start: dt.date, end: dt.date, timeout: int = 30) -> list[dict]:
    params = {
        "latitude": Config.MUMBAI_LAT,
        "longitude": Config.MUMBAI_LON,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": HOURLY,
        "timezone": "Asia/Kolkata",
    }
    resp = requests.get(ARCHIVE_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    return _rows_from_hourly(resp.json(), "open-meteo-archive")


def fetch_current(timeout: int = 20) -> dict | None:
    params = {
        "latitude": Config.MUMBAI_LAT,
        "longitude": Config.MUMBAI_LON,
        "current": "temperature_2m,relative_humidity_2m,precipitation",
        "timezone": "Asia/Kolkata",
    }
    resp = requests.get(CURRENT_URL, params=params, timeout=timeout)
    resp.raise_for_status()
    cur = resp.json().get("current", {})
    if not cur:
        return None
    return {
        "observed_at": cur["time"].replace("T", " "),
        "rainfall_mm": float(cur.get("precipitation") or 0),
        "temp_c": cur.get("temperature_2m"),
        "humidity": cur.get("relative_humidity_2m"),
        "source": "open-meteo-live",
    }


def load(rows: Iterable[dict]) -> int:
    return executemany(UPSERT, rows)


def backfill(days: int = 365) -> int:
    """Load the last `days` of real hourly weather for Mumbai."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    rows = fetch_archive(start, end)
    return load(rows)


def update_now() -> dict | None:
    """Fetch and store the current hour's weather."""
    row = fetch_current()
    if row:
        execute(UPSERT, row)
    return row


if __name__ == "__main__":
    print("Backfilling weather history ...")
    print("rows loaded:", backfill(365))
    print("current:", update_now())
