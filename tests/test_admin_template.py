import unittest
from unittest.mock import patch

import pandas as pd
from sqlalchemy.exc import ProgrammingError

from app import create_app
from app.routes import commuter


class AdminTemplateEmptyDataTest(unittest.TestCase):
    def test_renders_when_no_worst_hour(self):
        app = create_app()
        with app.test_request_context("/admin"):
            template = app.jinja_env.get_template("admin.html")
            html = template.render(
                kpis={
                    "avg_delay": 0,
                    "on_time_pct": 0,
                    "severe_delays": 0,
                    "worst_line": "-",
                },
                reliab=[],
                summary=[],
                risk=[],
                risk_label={"high": "High", "medium": "Moderate", "low": "Low"},
                hotspots=[],
                worst_hour={},
                month_names=[],
                monsoon_series={},
                heat_rows=[],
                wettest=[],
            )
            self.assertIn("Analytics dashboard", html)
            self.assertIn("No hourly delay data available yet", html)


class CommuterRouteEmptyDatabaseTest(unittest.TestCase):
    def test_commuter_handles_missing_lines_table(self):
        app = create_app()

        with app.app_context():
            from flask import g
            g.user = {"user_id": 99, "role_name": "commuter", "home_line_id": 2}

            with patch("app.routes.fetchone", side_effect=ProgrammingError("Table 'dhwani.lines' doesn't exist", None, None)):
                with patch("app.routes.queries.line_status", return_value={}), \
                     patch("app.routes.queries.delay_by_hour", return_value=pd.DataFrame(columns=["line_name", "hour_of_day", "avg_delay_min"])), \
                     patch("app.routes.queries.latest_risk", return_value=pd.DataFrame(columns=["line_id", "line_name"])):
                    with app.test_request_context("/commuter"):
                        response = commuter()
                        self.assertIn("Line unavailable", response)


class LoginRouteEmptyDatabaseTest(unittest.TestCase):
    def test_login_handles_missing_users_table(self):
        app = create_app()

        with app.test_request_context("/login", method="POST", data={"username": "priya", "password": "commuter123"}):
            with patch("app.auth.fetchone", side_effect=ProgrammingError("Table 'dhwani.users' doesn't exist", None, None)):
                response = app.view_functions["auth.login"]()
                self.assertIn("Database is not initialized yet", response)


if __name__ == "__main__":
    unittest.main()
