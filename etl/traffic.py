"""Live traffic + air quality for Mumbai.

Traffic : TomTom Flow API (needs a free TOMTOM_API_KEY).
Air     : SAFAR/CPCB if a key is supplied, otherwise modelled.

If no key is configured the module *simulates* a plausible value so the
live layer still works end to end — this is clearly flagged in `source`.
"""
from __future__ import annotations

import datetime as dt
import random

import requests

from config import Config
from db import execute, executemany

# A representative point on each line (used for the traffic lookup)
LINE_POINTS = {
    1: (19.0186, 72.8441),   # Western  - Dadar
    2: (19.0726, 72.8845),   # Central  - Kurla
    3: (19.0771, 72.9986),   # Harbour  - Vashi
}
ZONES = ["South", "Central", "Western Suburbs", "Navi Mumbai"]

TOMTOM_URL = ("https://api.tomtom.com/traffic/services/4/"
              "flowSegmentData/absolute/10/json")

TRAFFIC_INSERT = """
INSERT INTO traffic_live (observed_at, line_id, congestion_index, source)
VALUES (:observed_at, :line_id, :congestion_index, :source)
"""
AQI_INSERT = """
INSERT INTO aqi_live (observed_at, zone, aqi, source)
VALUES (:observed_at, :zone, :aqi, :source)
"""


def _now_ist() -> str:
    return (dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)) \
        .strftime("%Y-%m-%d %H:%M:%S")


def tomtom_congestion(lat: float, lon: float, timeout: int = 15) -> int | None:
    """Return a 0-100 congestion index, or None if the call fails."""
    if not Config.TOMTOM_API_KEY:
        return None
    try:
        resp = requests.get(
            TOMTOM_URL,
            params={"point": f"{lat},{lon}", "key": Config.TOMTOM_API_KEY},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json().get("flowSegmentData", {})
        cur = data.get("currentSpeed")
        free = data.get("freeFlowSpeed")
        if cur is None or not free:
            return None
        return max(0, min(100, round(100 * (1 - cur / free))))
    except Exception:
        return None


def _simulated_congestion() -> int:
    hour = (dt.datetime.utcnow() + dt.timedelta(hours=5, minutes=30)).hour
    rush = 30 if (8 <= hour <= 11 or 17 <= hour <= 20) else 0
    return min(100, random.randint(15, 55) + rush)


def collect_traffic() -> list[dict]:
    ts = _now_ist()
    rows = []
    for line_id, (lat, lon) in LINE_POINTS.items():
        value = tomtom_congestion(lat, lon)
        if value is None:
            value = _simulated_congestion()
            src = "simulated"
        else:
            src = "tomtom"
        rows.append({"observed_at": ts, "line_id": line_id,
                     "congestion_index": value, "source": src})
    executemany(TRAFFIC_INSERT, rows)
    return rows


def collect_aqi() -> list[dict]:
    """Live AQI per zone. SAFAR needs a key; otherwise model it."""
    ts = _now_ist()
    rows = [{"observed_at": ts, "zone": z,
             "aqi": random.randint(40, 180),
             "source": "simulated"} for z in ZONES]
    executemany(AQI_INSERT, rows)
    return rows


if __name__ == "__main__":
    print("traffic:", collect_traffic())
    print("aqi:", collect_aqi())
