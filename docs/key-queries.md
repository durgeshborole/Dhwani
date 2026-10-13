# Key SQL Queries

The interesting work lives in the database. These are the queries that carry
the project, and what each one demonstrates.

## 1. Line reliability with a ranking (window function)

```sql
SELECT
    line_name, records, avg_delay_min, max_delay_min, on_time_pct,
    RANK() OVER (ORDER BY avg_delay_min DESC) AS delay_rank,
    ROUND(AVG(avg_delay_min) OVER (), 1)      AS fleet_avg
FROM v_line_reliability
ORDER BY delay_rank;
```

`RANK()` orders the lines by how bad they are; `AVG() OVER ()` adds the
fleet-wide average on every row for comparison.

## 2. The monsoon finding — wet season vs dry season

```sql
SELECT
    line_name,
    ROUND(AVG(CASE WHEN month_no BETWEEN 6 AND 9
                   THEN avg_delay_min END), 1) AS monsoon_avg_delay,
    ROUND(AVG(CASE WHEN month_no NOT BETWEEN 6 AND 9
                   THEN avg_delay_min END), 1) AS dry_avg_delay
FROM v_monsoon_impact
GROUP BY line_name
ORDER BY (monsoon_avg_delay - dry_avg_delay) DESC;
```

`CASE WHEN` inside an aggregate pivots the year into two columns — the
project's headline number.

## 3. Monthly trend with a running total

```sql
SELECT
    month_no, month_name,
    ROUND(AVG(avg_delay_min), 1)                              AS avg_delay,
    ROUND(SUM(AVG(avg_delay_min)) OVER (ORDER BY month_no), 1) AS running_total
FROM v_monsoon_impact
GROUP BY month_no, month_name
ORDER BY month_no;
```

## 4. Worst hour on each line

```sql
SELECT line_name, hour_of_day, avg_delay_min
FROM v_delay_by_hour
ORDER BY avg_delay_min DESC
LIMIT 1;
```

## 5. Station hotspots

```sql
SELECT station_name, line_name, incidents, avg_delay_min
FROM v_station_hotspots
ORDER BY avg_delay_min DESC, incidents DESC
LIMIT 10;
```

## 6. The rain → delay join

```sql
SELECT w.obs_date, w.daily_rainfall_mm,
       ROUND(AVG(d.delay_minutes), 1) AS avg_delay_min
FROM v_daily_weather w
JOIN delay_records d ON d.run_date = w.obs_date
GROUP BY w.obs_date, w.daily_rainfall_mm
ORDER BY w.daily_rainfall_mm DESC
LIMIT 10;
```

## 7. The stored function (rainfall + hour → risk)

```sql
SELECT fn_risk_level(12.5, 9);   -- -> 'high'
```

Used by `etl/live.py` so the scoring rule lives in the database, not in Python.

## 8. The stored procedure (a report)

```sql
CALL sp_line_reliability(NULL);   -- all lines
CALL sp_line_reliability(1);      -- just line 1
```

## Views used by the app

| View | Purpose |
| --- | --- |
| `v_line_reliability` | avg / max delay and on-time % per line |
| `v_daily_weather` | hourly weather rolled up to a daily rainfall total |
| `v_monsoon_impact` | delay vs rainfall by month and line |
| `v_delay_by_hour` | average delay by hour of day |
| `v_station_hotspots` | which stations see the most delay |
| `v_latest_risk` | the newest delay-risk prediction per line |
