"""Command-line helper for the Dhwani project.

    python manage.py check                 # is the DB reachable + row counts
    python manage.py create-users          # (re)create the demo logins
    python manage.py etl-weather [days]    # backfill real weather (default 365)
    python manage.py etl-delays            # (re)build the delay history
    python manage.py etl-live              # run one live refresh pass
"""
from __future__ import annotations

import argparse
import sys

from werkzeug.security import generate_password_hash

import db


def cmd_check(_args) -> int:
    if not db.ping():
        print("X  Cannot reach the database. Check .env / MySQL is running.")
        return 1
    print("OK  Database reachable.")
    for label, sql in [
        ("lines", "SELECT COUNT(*) FROM `lines`"),
        ("stations", "SELECT COUNT(*) FROM stations"),
        ("trips", "SELECT COUNT(*) FROM trips"),
        ("weather_observations", "SELECT COUNT(*) FROM weather_observations"),
        ("delay_records", "SELECT COUNT(*) FROM delay_records"),
        ("delay_predictions", "SELECT COUNT(*) FROM delay_predictions"),
        ("users", "SELECT COUNT(*) FROM users"),
    ]:
        try:
            print(f"    {label:<22} {db.scalar(sql):>8,}")
        except Exception as e:
            print(f"    {label:<22}  (missing table: {e.__class__.__name__})")
    return 0


def cmd_create_users(_args) -> int:
    db.execute("INSERT IGNORE INTO roles (role_id, role_name) VALUES (1,'admin'),(2,'commuter')")
    line_id = db.scalar("SELECT line_id FROM `lines` ORDER BY line_id LIMIT 1")
    users = [
        ("admin", "admin123", "Asmita Jadhav", "admin@dhwani.local", 1, None),
        ("commuter", "commuter123", "Ravi Patil", "ravi@dhwani.local", 2, line_id),
        ("priya", "commuter123", "Priya Deshmukh", "priya@dhwani.local", 2, None),
    ]
    for u, pw, name, email, role, line in users:
        db.execute(
            """INSERT INTO users (username, password_hash, full_name, email,
                                  role_id, home_line_id)
               VALUES (:u, :p, :n, :e, :r, :l)
               ON DUPLICATE KEY UPDATE
                   password_hash = VALUES(password_hash),
                   full_name     = VALUES(full_name),
                   role_id       = VALUES(role_id),
                   home_line_id  = VALUES(home_line_id)""",
            {"u": u, "p": generate_password_hash(pw), "n": name,
             "e": email, "r": role, "l": line},
        )
        print(f"    user ready: {u} (role {role})")
    print("Demo passwords: admin123 / commuter123")
    return 0


def cmd_etl_weather(args) -> int:
    from etl import weather
    print(f"Backfilling {args.days} days of weather ...")
    n = weather.backfill(args.days)
    print(f"    weather rows loaded: {n}")
    print("    current hour:", weather.update_now())
    return 0


def cmd_etl_delays(_args) -> int:
    from etl import delays
    n = delays.build(samples_per_line=10)
    print(f"    delay rows inserted: {n}")
    print("    total delay records:", db.scalar("SELECT COUNT(*) FROM delay_records"))
    return 0


def cmd_etl_live(_args) -> int:
    from etl import live
    result = live.refresh()
    print("    rainfall now:", result["rainfall_mm"], "mm")
    for p in result["predictions"]:
        print(f"    line {p['line_id']}: {p['risk_level']} "
              f"(~{p['predicted_delay_min']} min)")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Dhwani helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("create-users").set_defaults(func=cmd_create_users)

    p = sub.add_parser("etl-weather"); p.add_argument("days", nargs="?", type=int, default=365)
    p.set_defaults(func=cmd_etl_weather)

    sub.add_parser("etl-delays").set_defaults(func=cmd_etl_delays)
    sub.add_parser("etl-live").set_defaults(func=cmd_etl_live)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
