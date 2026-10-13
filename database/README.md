# Dhwani — Database

Two files, run **in this order**:

| # | File | What it does |
| - | ---- | ------------ |
| 1 | `schema.sql` | drops/creates the `dhwani` database, all tables, indexes, views, the stored function and the stored procedure |
| 2 | `seed.sql` | loads the sample data (3 lines, 20 stations, 480 trips, 8,760 hourly weather rows, 10,950 delay records, 3 users) |

## Running in MySQL Workbench

1. Connect to your local server.
2. **File → Open SQL Script** → choose `schema.sql` → click the ⚡ (Execute) button.
3. Repeat with `seed.sql`.
4. Refresh the schemas panel — a `dhwani` database appears.

Both files are **safe to re-run**: `schema.sql` drops the database first, and
`seed.sql` truncates the tables before inserting.

## Verify it worked

```sql
USE dhwani;

SELECT COUNT(*) FROM delay_records;        -- 10950
SELECT * FROM v_line_reliability;          -- per-line reliability
SELECT * FROM v_latest_risk;               -- live risk per line
SELECT fn_risk_level(12.5, 9);             -- 'high'
CALL sp_line_reliability(NULL);            -- reliability report
```

## Gotcha: error 1418 on `fn_risk_level`

Creating a stored function needs the `log_bin_trust_function_creators` flag when
binary logging is on. If `schema.sql` fails there, run once as an admin:

```sql
SET GLOBAL log_bin_trust_function_creators = 1;
```

then re-run the function section (or the whole file).

## Regenerating the sample data

`seed.sql` is produced by `tools/generate_seed.py` (in the full project):

```bash
python tools/generate_seed.py
```

It uses a fixed random seed, so the data is reproducible.

## Data honesty

- Weather reflects Mumbai's real seasonal pattern; run the project's
  `manage.py etl-weather` to replace it with the **real** Open-Meteo archive.
- Delay records are **modelled** from the timetable plus rainfall, because
  Mumbai publishes no open delay feed. See `docs/problem-statement.md`.
