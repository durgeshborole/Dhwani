# ☔ Dhwani — Mumbai Suburban Rail Reliability & Monsoon Analytics

Dhwani is a **data platform** that studies how reliable Mumbai's suburban trains
really are, and how much the monsoon makes them late. It loads the railway
timetable and real rainfall history into a MySQL database, uses SQL to measure
where and when delays happen, adds a **live layer** (real weather, traffic and
air quality) to estimate current delay risk, and presents everything through a
web app with **two logins** — a simple *commuter* view and an analytics
*admin* dashboard.

> **Problem statement.** Mumbai's suburban railway carries over 7 million
> passengers a day and is frequently delayed — worst of all in the monsoon,
> when heavy rain slows entire lines. Commuters have no way to judge, right
> now, whether their line is at risk; planners have no quantified picture of
> where the delays concentrate. Dhwani makes that visible — historically and,
> where possible, live.

---

##  Features

- **MySQL star-ish schema** — lines, stations, trips, weather, delays, live
  traffic/AQI, predictions and users, with foreign keys, indexes and views.
- **Real weather data** — hourly rainfall for Mumbai from **Open-Meteo**
  (free, no API key).
- **Live layer** — current weather + traffic (TomTom, optional) + AQI feed a
  per-line **delay-risk score**.
- **Analytics in SQL** — joins, `GROUP BY`, **window functions**, conditional
  aggregation, a stored **function** and a stored **procedure**.
- **Dual-login web app** (Flask) — role-based access: *commuter* vs *admin*.
- **Dashboard** — KPIs, reliability ranking, monsoon-impact chart, hour-by-hour
  heat-map, station hotspots, live risk cards.

---

##  How it fits together

```
Open-Meteo (live+archive) ─┐
TomTom traffic (optional) ─┼─►  Python ETL  ─►  MySQL (dhwani)  ─►  SQL analytics  ─►  Flask app
AQI (modelled) ────────────┘                     │                      │                 │
Timetable (GTFS-style) ────► seed data ──────────┘                      │           commuter view
                                                                        └──────────  admin dashboard
```

1. **Load the database** — run `database/schema.sql` then `database/seed.sql`
   in MySQL Workbench.
2. **Refresh the data** — `manage.py etl-weather` pulls real rainfall,
   `etl-delays` rebuilds the delay history, `etl-live` scores the current risk.
3. **Analyse and view** — the Flask app reads the SQL views and renders the
   commuter and admin pages.

---

##  Tech stack

| Layer | Used |
| --- | --- |
| Language | Python 3.10+ |
| Database | **MySQL 8** (MariaDB 10.4+ also works) |
| Web | Flask, Jinja2, Chart.js |
| Data access | SQLAlchemy + PyMySQL |
| Data | pandas, requests |
| Live feeds | Open-Meteo (free), TomTom (optional) |

---

## Project structure

```
Dhwani/
├── database/
│   ├── schema.sql          # tables, indexes, views, function, procedure
│   └── seed.sql            # generated sample data (run after schema.sql)
├── docs/
│   ├── problem-statement.md
│   ├── er-diagram.md
│   └── key-queries.md
├── etl/
│   ├── weather.py          # Open-Meteo archive + current
│   ├── traffic.py          # live traffic + AQI
│   ├── delays.py           # build delay history from timetable + rainfall
│   └── live.py             # one live refresh pass
├── analytics/
│   └── queries.py          # every business question as SQL
├── app/
│   ├── __init__.py         # Flask app factory
│   ├── auth.py             # login + role-based access
│   ├── routes.py           # commuter + admin pages, JSON API
│   ├── templates/          # base, login, register, commuter, admin
│   └── static/style.css
├── tools/
│   └── generate_seed.py    # regenerates database/seed.sql
├── config.py               # reads .env
├── db.py                   # SQLAlchemy engine + query helpers
├── manage.py               # CLI: check / create-users / etl-*
├── run.py                  # start the web app
├── requirements.txt
└── .env.example
```

---

##  Setup

### 1. Create the database (MySQL Workbench)

1. Open MySQL Workbench and connect to your local server.
2. `File → Open SQL Script` → run **`database/schema.sql`**.
3. `File → Open SQL Script` → run **`database/seed.sql`**.

You now have a `dhwani` database with ~11,000 delay records, a year of hourly
weather, 480 trips and 3 users.

> **Note (stored function).** If creating `fn_risk_level` fails with error
> **1418** (binary logging), run once as an admin:
> `SET GLOBAL log_bin_trust_function_creators = 1;`

### 2. Set up Python

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure the connection

```bash
cp .env.example .env      # then edit DB_USER / DB_PASSWORD / SECRET_KEY
```

### 4. Check it

```bash
python manage.py check
```

### 5. Run the app

```bash
python run.py             # open http://127.0.0.1:5000
```

**Demo logins**

| Username | Password | Role | Sees |
| --- | --- | --- | --- |
| `admin` | `admin123` | admin | full analytics dashboard |
| `commuter` | `commuter123` | commuter | my-line status |
| `priya` | `commuter123` | commuter | my-line status |

> If you ever need to recreate the logins: `python manage.py create-users`

---

##  Refreshing the live data

```bash
python manage.py etl-weather 365   # real rainfall history (Open-Meteo)
python manage.py etl-delays        # rebuild the delay history
python manage.py etl-live          # score the current delay risk
```

Schedule `etl-live` every 10–15 minutes (cron on Linux, Task Scheduler on
Windows, or an EventBridge rule if deployed on AWS Lambda).

---

##  The SQL showcase

Everything interesting happens in the database. Highlights:

| Where | What it demonstrates |
| --- | --- |
| `v_line_reliability` | joins + `GROUP BY` + conditional aggregation for on-time % |
| `v_monsoon_impact` | joining delay facts to a daily-rainfall view |
| `line_reliability_ranked()` | `RANK() OVER (ORDER BY …)` and `AVG() OVER ()` |
| `monthly_trend()` | running total with a window function |
| `monsoon_summary()` | `CASE WHEN` inside aggregates (a manual pivot) |
| `fn_risk_level()` | a stored **function** turning rainfall+hour into a risk label |
| `sp_line_reliability()` | a stored **procedure** producing a report |

See `docs/key-queries.md` for the exact SQL.

---

## An honest note on the data

- **Weather is real** — pulled live from Open-Meteo for Mumbai.
- **Delays are modelled.** Mumbai publishes no open delay/GTFS-Realtime feed,
  so `etl/delays.py` *derives* a realistic delay history from the timetable
  plus the day's real rainfall. This relationship (rain → delay) is precisely
  what the project studies, and it is documented rather than hidden.
- **Traffic and AQI** use real APIs when a key is supplied, otherwise a
  modelled value (clearly marked in the `source` column).

---

##  Future work

- Plug in a real **GTFS-Realtime** feed if one becomes publicly available.
- Replace the modelled delay history with observed punctuality data.
- Add a forecasting model (R or scikit-learn) for next-hour delay.
- Deploy: RDS for MySQL, Lambda for `etl-live`, S3 for raw dumps.

---

## 👩‍💻 Author

**Asmita Jadhav** 

**Atharva Jadhav**

**Barun das**

**Chirag Chawade**

**Prasad Dahibaokar**

**Durgesh Borole**

**Garima Sahu**
