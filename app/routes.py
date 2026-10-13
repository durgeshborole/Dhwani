"""Page routes: a commuter view and an admin analytics dashboard."""
from __future__ import annotations

import pandas as pd
from flask import Blueprint, g, jsonify, redirect, render_template, url_for

from analytics import queries
from app.auth import login_required, role_required
from db import fetchone

main_bp = Blueprint("main", __name__)

RISK_LABEL = {"high": "High", "medium": "Moderate", "low": "Low"}


@main_bp.route("/")
def home():
    if g.user is None:
        return redirect(url_for("auth.login"))
    if g.user["role_name"] == "admin":
        return redirect(url_for("main.admin"))
    return redirect(url_for("main.commuter"))


# ---------------------------------------------------------------------
# Commuter view — the simple, live side
# ---------------------------------------------------------------------
@main_bp.route("/commuter")
@login_required
def commuter():
    line_id = g.user["home_line_id"] or 1
    line = {}

    try:
        line = fetchone(
            "SELECT line_id, line_name, operator FROM `lines` WHERE line_id = :l",
            {"l": line_id},
        ) or {}
    except Exception:
        line = {}

    if not line:
        try:
            fallback = fetchone(
                "SELECT line_id, line_name, operator FROM `lines` ORDER BY line_id LIMIT 1"
            )
        except Exception:
            fallback = None
        if fallback:
            line_id = int(fallback["line_id"])
            line = fallback
        else:
            line_id = 1
            line = {"line_id": 1, "line_name": "Line unavailable", "operator": "N/A"}

    try:
        status = queries.line_status(line_id)
    except Exception:
        status = {}

    try:
        hourly = queries.delay_by_hour()
    except Exception:
        hourly = pd.DataFrame(columns=["line_name", "hour_of_day", "avg_delay_min"])

    my_hourly = hourly[hourly["line_name"] == line.get("line_name", "")]

    worst_hour = None
    if not my_hourly.empty:
        worst_hour = int(my_hourly.loc[my_hourly["avg_delay_min"].idxmax(),
                                       "hour_of_day"])

    try:
        risk_all = queries.latest_risk()
        others = risk_all[risk_all["line_id"] != line_id].to_dict("records")
    except Exception:
        others = []

    try:
        recent = queries.recent_delays(line_id, 12).to_dict("records")
    except Exception:
        recent = []

    return render_template(
        "commuter.html",
        line=line,
        status=status,
        risk_label=RISK_LABEL.get(status.get("risk_level", "low"), "Low"),
        worst_hour=worst_hour,
        hours=my_hourly["hour_of_day"].tolist(),
        delays=my_hourly["avg_delay_min"].tolist(),
        recent=recent,
        others=others,
    )


# ---------------------------------------------------------------------
# Admin view — the analytics dashboard
# ---------------------------------------------------------------------
@main_bp.route("/admin")
@role_required("admin")
def admin():
    reliab = queries.line_reliability_ranked()
    monsoon = queries.monsoon_impact()
    summary = queries.monsoon_summary()
    heat = queries.delay_heatmap()
    hotspots = queries.station_hotspots(10)
    risk = queries.latest_risk()

    # chart payloads
    months = [str(m) for m in range(1, 13)]
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monsoon_series = {}
    for _, row in monsoon.iterrows():
        monsoon_series.setdefault(row["line_name"], {})[int(row["month_no"])] = \
            float(row["avg_delay_min"])

    heat_rows = []
    if not heat.empty:
        for line_name, series in heat.iterrows():
            heat_rows.append({
                "line": line_name,
                "values": [round(float(v), 1) if v == v else 0
                           for v in series.tolist()],
            })

    return render_template(
        "admin.html",
        kpis=queries.kpis(),
        reliab=reliab.to_dict("records"),
        summary=summary.to_dict("records"),
        risk=risk.to_dict("records"),
        risk_label=RISK_LABEL,
        hotspots=hotspots.to_dict("records"),
        worst_hour=queries.worst_hour(),
        month_names=month_names,
        monsoon_series=monsoon_series,
        heat_rows=heat_rows,
        wettest=queries.wettest_days(6).to_dict("records"),
    )


# ---------------------------------------------------------------------
# Small JSON API (handy for testing / extending the dashboard)
# ---------------------------------------------------------------------
@main_bp.route("/api/reliability")
@login_required
def api_reliability():
    return jsonify(queries.line_reliability_ranked().to_dict("records"))


@main_bp.route("/api/risk")
@login_required
def api_risk():
    return jsonify(queries.latest_risk().to_dict("records"))


@main_bp.route("/api/monsoon")
@login_required
def api_monsoon():
    return jsonify(queries.monsoon_summary().to_dict("records"))
