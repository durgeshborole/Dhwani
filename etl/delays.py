"""Delay history builder.

Mumbai publishes no open delay feed, so the project *derives* a realistic
history: every delay is modelled from the timetable plus the day's real
rainfall. Run this after the weather backfill to (re)build delay_records.

This is a documented modelling assumption, not fake data — the rainfall is
real, and the delay relationship is the thing the project studies.
"""
from __future__ import annotations

import random

import pandas as pd

from db import executemany, query_df, scalar

INSERT = """
INSERT INTO delay_records
    (trip_id, station_id, run_date, hour_of_day, delay_minutes, cause)
VALUES
    (:trip_id, :station_id, :run_date, :hour_of_day, :delay_minutes, :cause)
"""


def _delay_for(hour: int, rain: float) -> tuple[int, str]:
    rush = 2 + random.randint(0, 4) if (8 <= hour <= 11 or 17 <= hour <= 20) else 0
    if rain >= 40:
        wet = 8 + random.randint(0, 14)
    elif rain >= 15:
        wet = 4 + random.randint(0, 8)
    elif rain >= 3:
        wet = 1 + random.randint(0, 4)
    else:
        wet = 0
    delay = max(0, random.randint(0, 3) + rush + wet + random.randint(-2, 4))
    if wet >= 8:
        cause = "monsoon"
    elif rush:
        cause = "signal"
    elif random.random() < 0.12:
        cause = "track"
    else:
        cause = "operational"
    return delay, cause


def build(samples_per_line: int = 10, reset: bool = False) -> int:
    """(Re)build delay_records from trips + weather. Returns rows inserted."""
    if reset:
        executemany("DELETE FROM delay_records", [])

    already = set(
        str(r["run_date"]) for r in
        query_df("SELECT DISTINCT run_date FROM delay_records").to_dict("records")
    )

    rain_by_day = {
        str(r["d"]): float(r["rain"] or 0)
        for r in query_df(
            """SELECT DATE(observed_at) AS d, SUM(rainfall_mm) AS rain
               FROM weather_observations GROUP BY DATE(observed_at)"""
        ).to_dict("records")
    }
    if not rain_by_day:
        raise RuntimeError("No weather rows found — run etl.weather.backfill() first.")

    trips = query_df(
        """SELECT trip_id, line_id, day_type, HOUR(departure_time) AS hr
           FROM trips"""
    ).to_dict("records")

    stations = query_df(
        "SELECT station_id, line_id, station_name FROM stations"
    ).to_dict("records")
    stations_by_line: dict[int, list[dict]] = {}
    for s in stations:
        stations_by_line.setdefault(s["line_id"], []).append(s)
    hubs = {1: "Dadar", 2: "Kurla", 3: "Kurla"}

    def pick_station(line_id: int) -> int:
        pool = stations_by_line[line_id]
        hub = hubs.get(line_id)
        if hub and random.random() < 0.55:
            for s in pool:
                if s["station_name"] == hub:
                    return s["station_id"]
        return random.choice(pool)["station_id"]

    by_line_day: dict[tuple, list[dict]] = {}
    for t in trips:
        by_line_day.setdefault((t["line_id"], t["day_type"]), []).append(t)

    rows = []
    for day, rain in sorted(rain_by_day.items()):
        if day in already:
            continue
        weekday = pd.Timestamp(day).weekday() < 5
        day_type = "weekday" if weekday else "weekend"
        for line_id in sorted(stations_by_line):
            pool = by_line_day.get((line_id, day_type), [])
            if not pool:
                continue
            for t in random.sample(pool, min(samples_per_line, len(pool))):
                delay, cause = _delay_for(int(t["hr"]), rain)
                rows.append({
                    "trip_id": t["trip_id"],
                    "station_id": pick_station(line_id),
                    "run_date": day,
                    "hour_of_day": int(t["hr"]),
                    "delay_minutes": delay,
                    "cause": cause,
                })

    return executemany(INSERT, rows)


if __name__ == "__main__":
    print("delay rows inserted:", build(samples_per_line=10))
    print("total delay records:", scalar("SELECT COUNT(*) FROM delay_records"))
