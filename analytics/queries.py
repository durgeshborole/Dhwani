"""The analysis layer: every business question as a SQL query.

The heavy lifting is deliberately kept in SQL (views, joins, window
functions) — Python only calls it and shapes the result for charts.
"""
from __future__ import annotations

import pandas as pd

from db import fetchall, fetchone, query_df


# ---------------------------------------------------------------------
# Headline KPIs
# ---------------------------------------------------------------------
def kpis() -> dict:
    """Overall numbers for the admin dashboard header."""
    row = fetchone(
        """
        SELECT
            COUNT(*)                                        AS total_records,
            ROUND(AVG(delay_minutes), 1)                    AS avg_delay,
            ROUND(100 * SUM(delay_minutes <= 5) / COUNT(*), 1) AS on_time_pct,
            SUM(delay_minutes > 15)                         AS severe_delays
        FROM delay_records
        """
    ) or {}
    worst = fetchone(
        "SELECT line_name FROM v_line_reliability ORDER BY avg_delay_min DESC LIMIT 1"
    )
    return {
        "total_records": int(row.get("total_records") or 0),
        "avg_delay": float(row.get("avg_delay") or 0),
        "on_time_pct": float(row.get("on_time_pct") or 0),
        "severe_delays": int(row.get("severe_delays") or 0),
        "worst_line": (worst or {}).get("line_name", "-"),
    }


# ---------------------------------------------------------------------
# Reliability by line, with a window-function ranking
# ---------------------------------------------------------------------
def line_reliability_ranked() -> pd.DataFrame:
    return query_df(
        """
        SELECT
            line_name,
            records,
            avg_delay_min,
            max_delay_min,
            on_time_pct,
            RANK()       OVER (ORDER BY avg_delay_min DESC) AS delay_rank,
            ROUND(AVG(avg_delay_min) OVER (), 1)            AS fleet_avg
        FROM v_line_reliability
        ORDER BY delay_rank
        """
    )


# ---------------------------------------------------------------------
# Monsoon impact: delay vs rainfall, month by month, per line
# ---------------------------------------------------------------------
def monsoon_impact() -> pd.DataFrame:
    return query_df(
        """
        SELECT month_no, month_name, line_name,
               avg_daily_rainfall_mm, avg_delay_min
        FROM v_monsoon_impact
        ORDER BY month_no, line_name
        """
    )


def monsoon_summary() -> pd.DataFrame:
    """Wet season (Jun-Sep) versus the rest, per line — the headline finding."""
    return query_df(
        """
        SELECT
            line_name,
            ROUND(AVG(CASE WHEN month_no BETWEEN 6 AND 9
                           THEN avg_delay_min END), 1) AS monsoon_avg_delay,
            ROUND(AVG(CASE WHEN month_no NOT BETWEEN 6 AND 9
                           THEN avg_delay_min END), 1) AS dry_avg_delay
        FROM v_monsoon_impact
        GROUP BY line_name
        ORDER BY (monsoon_avg_delay - dry_avg_delay) DESC
        """
    )


# ---------------------------------------------------------------------
# Delay by hour of day
# ---------------------------------------------------------------------
def delay_by_hour() -> pd.DataFrame:
    return query_df(
        """
        SELECT line_name, hour_of_day, avg_delay_min
        FROM v_delay_by_hour
        ORDER BY line_name, hour_of_day
        """
    )


def delay_heatmap() -> pd.DataFrame:
    """Rows = line, columns = hour 0-23 (for a heat-map chart)."""
    df = delay_by_hour()
    if df.empty:
        return df
    return df.pivot(index="line_name", columns="hour_of_day", values="avg_delay_min")


def worst_hour() -> dict:
    return fetchone(
        """
        SELECT line_name, hour_of_day, avg_delay_min
        FROM v_delay_by_hour
        ORDER BY avg_delay_min DESC
        LIMIT 1
        """
    ) or {}


# ---------------------------------------------------------------------
# Station hotspots
# ---------------------------------------------------------------------
def station_hotspots(limit: int = 10) -> pd.DataFrame:
    return query_df(
        """
        SELECT station_name, line_name, incidents, avg_delay_min
        FROM v_station_hotspots
        ORDER BY avg_delay_min DESC, incidents DESC
        LIMIT :lim
        """,
        {"lim": limit},
    )


# ---------------------------------------------------------------------
# Live risk (commuter view + admin panel)
# ---------------------------------------------------------------------
def latest_risk() -> pd.DataFrame:
    return query_df(
        """
        SELECT line_id, line_name, predicted_at, rainfall_mm,
               predicted_delay_min, risk_level
        FROM v_latest_risk
        ORDER BY FIELD(risk_level, 'high', 'medium', 'low'), line_name
        """
    )


def line_status(line_id: int) -> dict:
    row = fetchone(
        """
        SELECT l.line_name, p.predicted_at, p.rainfall_mm,
               p.predicted_delay_min, p.risk_level
        FROM delay_predictions p
        JOIN `lines` l ON l.line_id = p.line_id
        WHERE p.line_id = :lid
        ORDER BY p.predicted_at DESC
        LIMIT 1
        """,
        {"lid": line_id},
    ) or {}
    return dict(row)


def recent_delays(line_id: int, limit: int = 12) -> pd.DataFrame:
    return query_df(
        """
        SELECT d.run_date, d.hour_of_day, s.station_name,
               d.delay_minutes, d.cause
        FROM delay_records d
        JOIN trips    t ON t.trip_id = d.trip_id
        JOIN stations s ON s.station_id = d.station_id
        WHERE t.line_id = :lid
        ORDER BY d.run_date DESC, d.hour_of_day DESC
        LIMIT :lim
        """,
        {"lid": line_id, "lim": limit},
    )


# ---------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------
def monthly_trend(line_id: int | None = None) -> pd.DataFrame:
    """Monthly average delay with a running total (window function)."""
    return query_df(
        """
        SELECT
            month_no,
            month_name,
            ROUND(AVG(avg_delay_min), 1)                       AS avg_delay,
            ROUND(SUM(AVG(avg_delay_min))
                  OVER (ORDER BY month_no), 1)                 AS running_total
        FROM v_monsoon_impact
        WHERE (:lid IS NULL OR line_name = (
                SELECT line_name FROM `lines` WHERE line_id = :lid))
        GROUP BY month_no, month_name
        ORDER BY month_no
        """,
        {"lid": line_id},
    )


def wettest_days(limit: int = 10) -> pd.DataFrame:
    return query_df(
        """
        SELECT w.obs_date, w.daily_rainfall_mm,
               ROUND(AVG(d.delay_minutes), 1) AS avg_delay_min
        FROM v_daily_weather w
        JOIN delay_records d ON d.run_date = w.obs_date
        GROUP BY w.obs_date, w.daily_rainfall_mm
        ORDER BY w.daily_rainfall_mm DESC
        LIMIT :lim
        """,
        {"lim": limit},
    )


def all_lines() -> list[dict]:
    return [dict(r) for r in fetchall(
        "SELECT line_id, line_name, operator FROM `lines` ORDER BY line_id"
    )]


def call_reliability_procedure(line_id: int | None = None) -> pd.DataFrame:
    """Runs the stored procedure sp_line_reliability."""
    return query_df("CALL sp_line_reliability(:lid)", {"lid": line_id})
