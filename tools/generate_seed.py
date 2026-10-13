#!/usr/bin/env python3
"""
Generate database/seed.sql for the Dhwani project.

Because Mumbai publishes no open live-delay feed, this script *derives*
realistic delay history from the timetable plus a monsoon-aware model.
Weather history is modelled on Mumbai's real seasonal pattern so the
analysis is meaningful; run etl/weather.py to replace it with the real
Open-Meteo archive.

Usage:
    python tools/generate_seed.py
"""
from __future__ import annotations

import datetime as dt
import os
import random

from werkzeug.security import generate_password_hash

random.seed(42)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "database", "seed.sql")

# ---------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------
LINES = [
    (1, "Western Line", "Western Railway", "blue"),
    (2, "Central Line", "Central Railway", "red"),
    (3, "Harbour Line", "Central Railway", "green"),
]

# (station_name, line_id, zone, lat, lon)
STATIONS = [
    # Western
    ("Churchgate",   1, "South",             18.9350, 72.8270),
    ("Mumbai Central", 1, "South",           18.9712, 72.8194),
    ("Dadar",        1, "Central",           19.0186, 72.8441),
    ("Bandra",       1, "Western Suburbs",   19.0544, 72.8402),
    ("Andheri",      1, "Western Suburbs",   19.1197, 72.8464),
    ("Borivali",     1, "Western Suburbs",   19.2307, 72.8567),
    ("Virar",        1, "Extended Suburbs",  19.4559, 72.8113),
    # Central
    ("CSMT",         2, "South",             18.9398, 72.8355),
    ("Byculla",      2, "Central",           18.9760, 72.8324),
    ("Dadar",        2, "Central",           19.0186, 72.8441),
    ("Kurla",        2, "Central",           19.0726, 72.8845),
    ("Ghatkopar",    2, "Central",           19.0860, 72.9081),
    ("Thane",        2, "Extended Suburbs",  19.1860, 72.9750),
    ("Kalyan",       2, "Extended Suburbs",  19.2437, 73.1355),
    # Harbour
    ("CSMT",         3, "South",             18.9398, 72.8355),
    ("Wadala",       3, "Central",           19.0176, 72.8560),
    ("Kurla",        3, "Central",           19.0726, 72.8845),
    ("Vashi",        3, "Navi Mumbai",       19.0771, 72.9986),
    ("Nerul",        3, "Navi Mumbai",       19.0330, 73.0186),
    ("Panvel",       3, "Navi Mumbai",       18.9894, 73.1175),
]

# Hub stations used most often when recording a delay
HUBS = {1: "Dadar", 2: "Kurla", 3: "Kurla"}

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def sql_str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def batched(rows, size=500):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def write(lines_list, fh):
    fh.write("\n".join(lines_list))
    fh.write("\n")


# ---------------------------------------------------------------------
# Generate the year of hourly weather (Mumbai seasonality)
# ---------------------------------------------------------------------
END = dt.date(2026, 9, 30)
START = dt.date(2025, 10, 1)

daily_rain = {}          # date -> total mm
weather_rows = []        # (datetime, rain, temp, humidity)

day = START
while day <= END:
    month = day.month
    monsoon = month in (6, 7, 8, 9)
    day_total = 0.0
    for hour in range(24):
        if monsoon:
            # Most monsoon hours are light; some are very heavy.
            r = 0.0
            if random.random() < 0.30:
                r = round(random.expovariate(1 / 6.0), 2)          # light-medium
            if random.random() < 0.06:
                r = round(random.uniform(20, 70), 2)               # cloudburst
            temp = round(random.uniform(25, 31), 2)
            hum = random.randint(78, 96)
        else:
            r = round(random.uniform(0, 1.5), 2) if random.random() < 0.08 else 0.0
            temp = round(random.uniform(24, 36), 2)
            hum = random.randint(45, 75)
        day_total += r
        ts = dt.datetime.combine(day, dt.time(hour, 0))
        weather_rows.append((ts.strftime("%Y-%m-%d %H:%M:%S"), r, temp, hum))
    daily_rain[day] = round(day_total, 2)
    day += dt.timedelta(days=1)

# ---------------------------------------------------------------------
# Trips: every 15 minutes, 04:00 -> 23:45, per line and day type
# ---------------------------------------------------------------------
trip_rows = []          # (trip_id, line_id, direction, day_type, dep, arr)
trips_by_line_day = {}  # (line_id, day_type) -> list of (trip_id, hour)
tid = 0
for line_id, _, _, _ in LINES:
    for day_type in ("weekday", "weekend"):
        trips_by_line_day[(line_id, day_type)] = []
        start = dt.datetime(2026, 1, 1, 4, 0)
        for n in range(80):                    # 04:00 .. 23:45, every 15 min
            t = start + dt.timedelta(minutes=15 * n)
            tid += 1
            dep = t.strftime("%H:%M:%S")
            arr = (t + dt.timedelta(minutes=62)).strftime("%H:%M:%S")
            direction = "UP" if (tid % 2 == 0) else "DOWN"
            trip_rows.append((tid, line_id, direction, day_type, dep, arr))
            trips_by_line_day[(line_id, day_type)].append((tid, t.hour))

# ---------------------------------------------------------------------
# Delay records: derived from hour + rainfall
# ---------------------------------------------------------------------
station_ids = {}         # (name, line_id) -> station_id
sid = 0
station_rows = []
for name, line_id, zone, lat, lon in STATIONS:
    sid += 1
    station_rows.append((sid, name, line_id, zone, lat, lon))
    station_ids[(name, line_id)] = sid


def station_of(line_id: int) -> int:
    """Return a station id for the line, weighted towards its hub."""
    hub = HUBS[line_id]
    if random.random() < 0.55:
        return station_ids[(hub, line_id)]
    name = random.choice([s[0] for s in STATIONS if s[1] == line_id])
    return station_ids[(name, line_id)]


delay_rows = []
rec = 0
day = START
while day <= END:
    rain = daily_rain[day]
    weekday = day.weekday() < 5
    for line_id, _, _, _ in LINES:
        pool = trips_by_line_day[(line_id, "weekday" if weekday else "weekend")]
        for trip_id, hour in random.sample(pool, 10):
            rush = 2 + random.randint(0, 4) if (8 <= hour <= 11 or 17 <= hour <= 20) else 0
            if rain >= 40:
                wet = 8 + random.randint(0, 14)
            elif rain >= 15:
                wet = 4 + random.randint(0, 8)
            elif rain >= 3:
                wet = 1 + random.randint(0, 4)
            else:
                wet = 0
            base = random.randint(0, 3)
            delay = max(0, base + rush + wet + random.randint(-2, 4))
            if wet >= 8:
                cause = "monsoon"
            elif rush:
                cause = "signal"
            elif random.random() < 0.12:
                cause = "track"
            else:
                cause = "operational"
            rec += 1
            delay_rows.append((rec, trip_id, station_of(line_id), day.isoformat(),
                               hour, delay, cause))
    day += dt.timedelta(days=1)

# ---------------------------------------------------------------------
# Live-ish tables (last 24 hours)
# ---------------------------------------------------------------------
now = dt.datetime(2026, 10, 13, 18, 0)
traffic_rows, aqi_rows, pred_rows = [], [], []
for h in range(24):
    ts = (now - dt.timedelta(hours=h)).strftime("%Y-%m-%d %H:%M:%S")
    for line_id, _, _, _ in LINES:
        traffic_rows.append((line_id, ts, random.randint(20, 85)))
    for zone in ("South", "Central", "Western Suburbs", "Navi Mumbai"):
        aqi_rows.append((zone, ts, random.randint(40, 180)))

for h in range(24):
    ts_dt = now - dt.timedelta(hours=h)
    ts = ts_dt.strftime("%Y-%m-%d %H:%M:%S")
    hour = ts_dt.hour
    for line_id, _, _, _ in LINES:
        rain = round(random.uniform(0, 12) if hour in (8, 9, 10, 17, 18, 19) else
                     random.uniform(0, 4), 2)
        score = (3 if rain >= 20 else 2 if rain >= 5 else 1 if rain >= 1 else 0)
        if 8 <= hour <= 11 or 17 <= hour <= 20:
            score += 2
        risk = "high" if score >= 4 else "medium" if score >= 2 else "low"
        pred = int(rain * 0.9) + (6 if risk == "high" else 3 if risk == "medium" else 1)
        pred_rows.append((line_id, ts, hour, rain, pred, risk))

# ---------------------------------------------------------------------
# Users (dual login)
# ---------------------------------------------------------------------
admin_hash = generate_password_hash("admin123")
commuter_hash = generate_password_hash("commuter123")
user_rows = [
    (1, "admin", admin_hash, "Asmita Jadhav", "admin@dhwani.local", 1, None),
    (2, "commuter", commuter_hash, "Ravi Patil", "ravi@dhwani.local", 2, 1),
    (3, "priya", commuter_hash, "Priya Deshmukh", "priya@dhwani.local", 2, 2),
]

# ---------------------------------------------------------------------
# Emit SQL
# ---------------------------------------------------------------------
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("-- =====================================================================\n")
    fh.write("--  DHWANI - seed data (generated by tools/generate_seed.py)\n")
    fh.write("--  Run database/schema.sql FIRST, then run this file.\n")
    fh.write("--  Safe to re-run: it truncates the data tables before inserting.\n")
    fh.write("-- =====================================================================\n\n")
    fh.write("USE dhwani;\n\n")
    fh.write("SET FOREIGN_KEY_CHECKS = 0;\n")
    for tbl in ("delay_predictions", "delay_records", "traffic_live", "aqi_live",
                "weather_observations", "trips", "stations", "`lines`", "users", "roles"):
        fh.write(f"TRUNCATE TABLE {tbl};\n")
    fh.write("SET FOREIGN_KEY_CHECKS = 1;\n\n")

    # roles
    fh.write("-- Roles ---------------------------------------------------------------\n")
    write(["INSERT INTO roles (role_id, role_name) VALUES "
           "(1, 'admin'), (2, 'commuter');"], fh)

    # lines
    fh.write("\n-- Lines ---------------------------------------------------------------\n")
    write(["INSERT INTO `lines` (line_id, line_name, operator, colour) VALUES"]
          + [f"  ({i}, {sql_str(n)}, {sql_str(o)}, {sql_str(c)})"
             + ("," if k < len(LINES) - 1 else ";")
             for k, (i, n, o, c) in enumerate(LINES)], fh)

    # stations
    fh.write("\n-- Stations ------------------------------------------------------------\n")
    rows = [f"({i}, {sql_str(n)}, {li}, {sql_str(z)}, {lat}, {lon})"
            for (i, n, li, z, lat, lon) in station_rows]
    for chunk in batched(rows, 50):
        write(["INSERT INTO stations (station_id, station_name, line_id, zone, latitude, longitude) VALUES",
               "  " + ",\n  ".join(chunk) + ";"], fh)

    # trips
    fh.write("\n-- Trips (timetable) ---------------------------------------------------\n")
    rows = [f"({i}, {li}, {sql_str(d)}, {sql_str(dt_)}, {sql_str(dep)}, {sql_str(arr)})"
            for (i, li, d, dt_, dep, arr) in trip_rows]
    for chunk in batched(rows, 300):
        write(["INSERT INTO trips (trip_id, line_id, direction, day_type, departure_time, arrival_time) VALUES",
               "  " + ",\n  ".join(chunk) + ";"], fh)

    # weather
    fh.write("\n-- Weather observations (hourly) --------------------------------------\n")
    rows = [f"({sql_str(ts)}, {r}, {t}, {h})" for (ts, r, t, h) in weather_rows]
    for chunk in batched(rows, 500):
        write(["INSERT INTO weather_observations (observed_at, rainfall_mm, temp_c, humidity) VALUES",
               "  " + ",\n  ".join(chunk) + ";"], fh)

    # delays
    fh.write("\n-- Delay records (derived history) ------------------------------------\n")
    rows = [f"({i}, {tr}, {st}, {sql_str(d)}, {h}, {dl}, {sql_str(c)})"
            for (i, tr, st, d, h, dl, c) in delay_rows]
    for chunk in batched(rows, 500):
        write(["INSERT INTO delay_records (record_id, trip_id, station_id, run_date, hour_of_day, delay_minutes, cause) VALUES",
               "  " + ",\n  ".join(chunk) + ";"], fh)

    # traffic
    fh.write("\n-- Live traffic -------------------------------------------------------\n")
    rows = [f"({li}, {sql_str(ts)}, {ci})" for (li, ts, ci) in traffic_rows]
    for chunk in batched(rows, 200):
        write(["INSERT INTO traffic_live (line_id, observed_at, congestion_index) VALUES",
               "  " + ",\n  ".join(chunk) + ";"], fh)

    # aqi
    fh.write("\n-- Live AQI -----------------------------------------------------------\n")
    rows = [f"({sql_str(z)}, {sql_str(ts)}, {a})" for (z, ts, a) in aqi_rows]
    for chunk in batched(rows, 200):
        write(["INSERT INTO aqi_live (zone, observed_at, aqi) VALUES",
               "  " + ",\n  ".join(chunk) + ";"], fh)

    # predictions
    fh.write("\n-- Delay predictions --------------------------------------------------\n")
    rows = [f"({li}, {sql_str(ts)}, {h}, {r}, {p}, {sql_str(risk)})"
            for (li, ts, h, r, p, risk) in pred_rows]
    for chunk in batched(rows, 200):
        write(["INSERT INTO delay_predictions (line_id, predicted_at, hour_of_day, rainfall_mm, predicted_delay_min, risk_level) VALUES",
               "  " + ",\n  ".join(chunk) + ";"], fh)

    # users
    fh.write("\n-- Users (passwords: admin123 / commuter123) --------------------------\n")
    rows = [f"({i}, {sql_str(u)}, {sql_str(pw)}, {sql_str(fn)}, {sql_str(em)}, {r}, "
            f"{'NULL' if hl is None else hl})"
            for (i, u, pw, fn, em, r, hl) in user_rows]
    write(["INSERT INTO users (user_id, username, password_hash, full_name, email, role_id, home_line_id) VALUES",
           "  " + ",\n  ".join(rows) + ";"], fh)

    fh.write("\n-- Done. Summary:\n")
    fh.write(f"--   lines={len(LINES)} stations={len(station_rows)} trips={len(trip_rows)} "
             f"weather={len(weather_rows)} delays={len(delay_rows)} users={len(user_rows)}\n")

print(f"Wrote {os.path.abspath(OUT)}")
print(f"  lines={len(LINES)}  stations={len(station_rows)}  trips={len(trip_rows)}")
print(f"  weather={len(weather_rows)}  delays={len(delay_rows)}  users={len(user_rows)}")
