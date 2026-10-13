"""The live layer — one pass that refreshes everything 'now'.

Order of work:
  1. pull current weather (Open-Meteo, free)
  2. pull live traffic and AQI
  3. score each line's delay risk and write delay_predictions

The risk label itself comes from the database's own stored function
`fn_risk_level`, so the scoring rule lives in SQL, not scattered in Python.
Schedule this every 10-15 minutes (cron / Task Scheduler / Lambda).
"""
from __future__ import annotations

import datetime as dt

from db import execute, executemany, scalar
from etl import traffic, weather

PRED_INSERT = """
INSERT INTO delay_predictions
    (line_id, predicted_at, hour_of_day, rainfall_mm,
     predicted_delay_min, risk_level)
VALUES
    (:line_id, :predicted_at, :hour_of_day, :rainfall_mm,
     :predicted_delay_min, :risk_level)
"""


def _now_ist() -> dt.datetime:
    return dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)


def latest_rainfall() -> float:
    """Rainfall from the most recent weather row (0 if none)."""
    val = scalar(
        "SELECT rainfall_mm FROM weather_observations "
        "ORDER BY observed_at DESC LIMIT 1"
    )
    return float(val or 0)


def refresh(lat: float | None = None, lon: float | None = None) -> dict:
    """Run the whole live pass. Returns a small summary."""
    # 1. weather
    wrow = weather.update_now()

    # 2. traffic + aqi
    traffic.collect_traffic()
    traffic.collect_aqi()

    # 3. score each line
    now = _now_ist()
    rain = latest_rainfall()
    lines = [r["line_id"] for r in
             __import__("db").fetchall("SELECT line_id FROM `lines` ORDER BY line_id")]

    rows = []
    for line_id in lines:
        hour = now.hour
        risk = scalar("SELECT fn_risk_level(:r, :h)", {"r": rain, "h": hour})
        predicted = int(rain * 0.9) + (
            6 if risk == "high" else 3 if risk == "medium" else 1
        )
        rows.append({
            "line_id": line_id,
            "predicted_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "hour_of_day": hour,
            "rainfall_mm": rain,
            "predicted_delay_min": predicted,
            "risk_level": risk,
        })
    executemany(PRED_INSERT, rows)

    return {"weather": wrow, "rainfall_mm": rain, "predictions": rows}


if __name__ == "__main__":
    print(refresh())
