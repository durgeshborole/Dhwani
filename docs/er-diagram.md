# Entity-Relationship Diagram

```mermaid
erDiagram
    roles ||--o{ users : "grants"
    lines ||--o{ users : "home line"
    lines ||--o{ stations : "has"
    lines ||--o{ trips : "schedules"
    lines ||--o{ traffic_live : "measured on"
    lines ||--o{ delay_predictions : "scored for"

    trips ||--o{ delay_records : "measured in"
    stations ||--o{ delay_records : "occurs at"

    roles {
        tinyint  role_id   PK
        varchar  role_name
    }
    users {
        int      user_id       PK
        varchar  username      UK
        varchar  password_hash
        varchar  full_name
        varchar  email         UK
        tinyint  role_id       FK
        int      home_line_id  FK
        datetime created_at
    }
    lines {
        int      line_id   PK
        varchar  line_name UK
        varchar  operator
        varchar  colour
    }
    stations {
        int      station_id   PK
        varchar  station_name
        int      line_id      FK
        varchar  zone
        decimal  latitude
        decimal  longitude
    }
    trips {
        int      trip_id        PK
        int      line_id        FK
        enum     direction
        enum     day_type
        time     departure_time
        time     arrival_time
    }
    weather_observations {
        bigint   obs_id      PK
        datetime observed_at UK
        decimal  rainfall_mm
        decimal  temp_c
        tinyint  humidity
        varchar  source
    }
    delay_records {
        bigint   record_id     PK
        int      trip_id       FK
        int      station_id    FK
        date     run_date
        tinyint  hour_of_day
        smallint delay_minutes
        varchar  cause
    }
    traffic_live {
        bigint   traffic_id       PK
        datetime observed_at
        int      line_id          FK
        tinyint  congestion_index
        varchar  source
    }
    aqi_live {
        bigint   aqi_id      PK
        datetime observed_at
        varchar  zone
        smallint aqi
        varchar  source
    }
    delay_predictions {
        bigint   pred_id             PK
        int      line_id             FK
        datetime predicted_at
        tinyint  hour_of_day
        decimal  rainfall_mm
        smallint predicted_delay_min
        enum     risk_level
    }
```

## Notes

- `stations` has a unique key on `(station_name, line_id)`, so interchange
  stations like **Dadar** and **Kurla** appear once per line they serve.
- `delay_records` is the central fact table: one row = one trip measured at one
  station on one date.
- `weather_observations` is unique per hour, which makes the ETL a safe upsert.
- Views (`v_line_reliability`, `v_monsoon_impact`, `v_delay_by_hour`,
  `v_station_hotspots`, `v_daily_weather`, `v_latest_risk`) sit on top of these
  tables and are what the app queries.
