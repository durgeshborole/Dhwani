-- =====================================================================
--  DHWANI  -  Mumbai Suburban Rail Reliability & Monsoon Analytics
--  database/schema.sql
--
--  Target   : MySQL 8.x  (also runs on MariaDB 10.4+)
--  How to run in MySQL Workbench:
--      1. Open a new SQL tab connected to your server.
--      2. File > Open SQL Script  ->  select this file.
--      3. Click the lightning bolt to execute the whole script.
--      4. Then do the same with database/seed.sql.
--
--  The script is safe to re-run: it drops and recreates the schema.
-- =====================================================================

DROP DATABASE IF EXISTS dhwani;
CREATE DATABASE dhwani
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
USE dhwani;

-- ---------------------------------------------------------------------
-- 1. LOOKUP TABLES
-- ---------------------------------------------------------------------

CREATE TABLE roles (
    role_id   TINYINT      NOT NULL,
    role_name VARCHAR(20)  NOT NULL,
    PRIMARY KEY (role_id),
    UNIQUE KEY uq_role_name (role_name)
) ENGINE=InnoDB;

CREATE TABLE `lines` (
    line_id   INT          NOT NULL AUTO_INCREMENT,
    line_name VARCHAR(50)  NOT NULL,
    operator  VARCHAR(50)  NOT NULL,
    colour    VARCHAR(20)  NOT NULL DEFAULT 'grey',
    PRIMARY KEY (line_id),
    UNIQUE KEY uq_line_name (line_name)
) ENGINE=InnoDB;

CREATE TABLE stations (
    station_id   INT          NOT NULL AUTO_INCREMENT,
    station_name VARCHAR(80)  NOT NULL,
    line_id      INT          NOT NULL,
    zone         VARCHAR(30)  NOT NULL,
    latitude     DECIMAL(9,6) NULL,
    longitude    DECIMAL(9,6) NULL,
    PRIMARY KEY (station_id),
    UNIQUE KEY uq_station_per_line (station_name, line_id),
    KEY idx_station_line (line_id),
    CONSTRAINT fk_station_line
        FOREIGN KEY (line_id) REFERENCES `lines` (line_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. SCHEDULE (GTFS-style, simplified)
-- ---------------------------------------------------------------------

CREATE TABLE trips (
    trip_id        INT          NOT NULL AUTO_INCREMENT,
    line_id        INT          NOT NULL,
    direction      ENUM('UP','DOWN')            NOT NULL,
    day_type       ENUM('weekday','weekend')    NOT NULL,
    departure_time TIME         NOT NULL,
    arrival_time   TIME         NOT NULL,
    PRIMARY KEY (trip_id),
    KEY idx_trip_line_day (line_id, day_type),
    CONSTRAINT fk_trip_line
        FOREIGN KEY (line_id) REFERENCES `lines` (line_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 3. OBSERVED / DERIVED FACTS
-- ---------------------------------------------------------------------

-- Hourly weather. Feeds the monsoon analysis and the live risk score.
CREATE TABLE weather_observations (
    obs_id      BIGINT       NOT NULL AUTO_INCREMENT,
    observed_at DATETIME     NOT NULL,
    rainfall_mm DECIMAL(6,2) NOT NULL DEFAULT 0.00,
    temp_c      DECIMAL(5,2) NULL,
    humidity    TINYINT      NULL,
    source      VARCHAR(30)  NOT NULL DEFAULT 'open-meteo',
    PRIMARY KEY (obs_id),
    UNIQUE KEY uq_weather_time (observed_at),
    KEY idx_weather_date (observed_at)
) ENGINE=InnoDB;

-- One row = one trip measured at one station on one date.
CREATE TABLE delay_records (
    record_id     BIGINT      NOT NULL AUTO_INCREMENT,
    trip_id       INT         NOT NULL,
    station_id    INT         NOT NULL,
    run_date      DATE        NOT NULL,
    hour_of_day   TINYINT     NOT NULL,
    delay_minutes SMALLINT    NOT NULL,
    cause         VARCHAR(30) NOT NULL DEFAULT 'unknown',
    PRIMARY KEY (record_id),
    KEY idx_delay_date (run_date),
    KEY idx_delay_hour (hour_of_day),
    KEY idx_delay_trip (trip_id),
    KEY idx_delay_station (station_id),
    CONSTRAINT fk_delay_trip
        FOREIGN KEY (trip_id) REFERENCES trips (trip_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_delay_station
        FOREIGN KEY (station_id) REFERENCES stations (station_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- Live road-congestion index per line (TomTom / HERE, or simulated).
CREATE TABLE traffic_live (
    traffic_id       BIGINT      NOT NULL AUTO_INCREMENT,
    observed_at      DATETIME    NOT NULL,
    line_id          INT         NOT NULL,
    congestion_index TINYINT     NOT NULL,
    source           VARCHAR(30) NOT NULL DEFAULT 'tomtom',
    PRIMARY KEY (traffic_id),
    KEY idx_traffic_line_time (line_id, observed_at),
    CONSTRAINT fk_traffic_line
        FOREIGN KEY (line_id) REFERENCES `lines` (line_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- Live air-quality index per zone (SAFAR / MPCB, or simulated).
CREATE TABLE aqi_live (
    aqi_id      BIGINT      NOT NULL AUTO_INCREMENT,
    observed_at DATETIME    NOT NULL,
    zone        VARCHAR(30) NOT NULL,
    aqi         SMALLINT    NOT NULL,
    source      VARCHAR(30) NOT NULL DEFAULT 'safar',
    PRIMARY KEY (aqi_id),
    KEY idx_aqi_zone_time (zone, observed_at)
) ENGINE=InnoDB;

-- Output of the live scoring step: current delay risk per line.
CREATE TABLE delay_predictions (
    pred_id             BIGINT      NOT NULL AUTO_INCREMENT,
    line_id             INT         NOT NULL,
    predicted_at        DATETIME    NOT NULL,
    hour_of_day         TINYINT     NOT NULL,
    rainfall_mm         DECIMAL(6,2) NOT NULL,
    predicted_delay_min SMALLINT    NOT NULL,
    risk_level          ENUM('low','medium','high') NOT NULL,
    PRIMARY KEY (pred_id),
    KEY idx_pred_line_time (line_id, predicted_at),
    CONSTRAINT fk_pred_line
        FOREIGN KEY (line_id) REFERENCES `lines` (line_id)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. APPLICATION USERS  (dual login: commuter + admin)
-- ---------------------------------------------------------------------

CREATE TABLE users (
    user_id       INT          NOT NULL AUTO_INCREMENT,
    username      VARCHAR(50)  NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(80)  NOT NULL,
    email         VARCHAR(120) NULL,
    role_id       TINYINT      NOT NULL,
    home_line_id  INT          NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id),
    UNIQUE KEY uq_username (username),
    UNIQUE KEY uq_email (email),
    KEY idx_user_role (role_id),
    CONSTRAINT fk_user_role
        FOREIGN KEY (role_id) REFERENCES roles (role_id)
        ON UPDATE CASCADE,
    CONSTRAINT fk_user_line
        FOREIGN KEY (home_line_id) REFERENCES `lines` (line_id)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- =====================================================================
-- 5. VIEWS  - the reusable analysis layer
-- =====================================================================

DROP VIEW IF EXISTS v_line_reliability;
CREATE VIEW v_line_reliability AS
SELECT
    l.line_id,
    l.line_name,
    COUNT(*)                                                   AS records,
    ROUND(AVG(d.delay_minutes), 1)                             AS avg_delay_min,
    MAX(d.delay_minutes)                                       AS max_delay_min,
    ROUND(100 * SUM(CASE WHEN d.delay_minutes <= 5 THEN 1 ELSE 0 END)
          / COUNT(*), 1)                                       AS on_time_pct
FROM delay_records d
JOIN trips  t ON t.trip_id = d.trip_id
JOIN `lines`  l ON l.line_id = t.line_id
GROUP BY l.line_id, l.line_name;

DROP VIEW IF EXISTS v_daily_weather;
CREATE VIEW v_daily_weather AS
SELECT
    DATE(observed_at)                AS obs_date,
    ROUND(SUM(rainfall_mm), 2)       AS daily_rainfall_mm
FROM weather_observations
GROUP BY DATE(observed_at);

DROP VIEW IF EXISTS v_monsoon_impact;
CREATE VIEW v_monsoon_impact AS
SELECT
    l.line_name,
    MONTH(d.run_date)          AS month_no,
    MONTHNAME(d.run_date)      AS month_name,
    ROUND(AVG(w.daily_rainfall_mm), 2) AS avg_daily_rainfall_mm,
    ROUND(AVG(d.delay_minutes), 1)     AS avg_delay_min
FROM delay_records d
JOIN trips  t ON t.trip_id = d.trip_id
JOIN `lines`  l ON l.line_id = t.line_id
LEFT JOIN v_daily_weather w ON w.obs_date = d.run_date
GROUP BY l.line_id, l.line_name, MONTH(d.run_date), MONTHNAME(d.run_date);

DROP VIEW IF EXISTS v_delay_by_hour;
CREATE VIEW v_delay_by_hour AS
SELECT
    l.line_name,
    d.hour_of_day,
    COUNT(*)                       AS records,
    ROUND(AVG(d.delay_minutes), 1) AS avg_delay_min
FROM delay_records d
JOIN trips t ON t.trip_id = d.trip_id
JOIN `lines` l ON l.line_id = t.line_id
GROUP BY l.line_id, l.line_name, d.hour_of_day;

DROP VIEW IF EXISTS v_station_hotspots;
CREATE VIEW v_station_hotspots AS
SELECT
    s.station_id,
    s.station_name,
    l.line_name,
    COUNT(*)                       AS incidents,
    ROUND(AVG(d.delay_minutes), 1) AS avg_delay_min
FROM delay_records d
JOIN stations s ON s.station_id = d.station_id
JOIN `lines`    l ON l.line_id = s.line_id
GROUP BY s.station_id, s.station_name, l.line_id, l.line_name;

DROP VIEW IF EXISTS v_latest_risk;
CREATE VIEW v_latest_risk AS
SELECT
    l.line_id,
    l.line_name,
    p.predicted_at,
    p.rainfall_mm,
    p.predicted_delay_min,
    p.risk_level
FROM delay_predictions p
JOIN `lines` l ON l.line_id = p.line_id
JOIN (
    SELECT line_id, MAX(predicted_at) AS mx
    FROM delay_predictions
    GROUP BY line_id
) latest ON latest.line_id = p.line_id AND latest.mx = p.predicted_at;

-- =====================================================================
-- 6. STORED FUNCTION  - rainfall + hour -> risk level
-- =====================================================================

DROP FUNCTION IF EXISTS fn_risk_level;
DELIMITER $$
CREATE FUNCTION fn_risk_level(p_rainfall DECIMAL(6,2), p_hour TINYINT)
RETURNS VARCHAR(10)
DETERMINISTIC
BEGIN
    DECLARE v_score INT DEFAULT 0;

    IF p_rainfall >= 20 THEN SET v_score = v_score + 3;
    ELSEIF p_rainfall >= 5 THEN SET v_score = v_score + 2;
    ELSEIF p_rainfall >= 1 THEN SET v_score = v_score + 1;
    END IF;

    IF (p_hour BETWEEN 8 AND 11) OR (p_hour BETWEEN 17 AND 20) THEN
        SET v_score = v_score + 2;
    END IF;

    IF v_score >= 4 THEN RETURN 'high';
    ELSEIF v_score >= 2 THEN RETURN 'medium';
    ELSE RETURN 'low';
    END IF;
END$$
DELIMITER ;

-- =====================================================================
-- 7. STORED PROCEDURE  - reliability report for one line (or all)
-- =====================================================================

DROP PROCEDURE IF EXISTS sp_line_reliability;
DELIMITER $$
CREATE PROCEDURE sp_line_reliability(IN p_line_id INT)
BEGIN
    SELECT
        l.line_name,
        COUNT(*)                       AS records,
        ROUND(AVG(d.delay_minutes), 1) AS avg_delay_min,
        ROUND(100 * SUM(CASE WHEN d.delay_minutes <= 5 THEN 1 ELSE 0 END)
              / COUNT(*), 1)           AS on_time_pct
    FROM delay_records d
    JOIN trips t ON t.trip_id = d.trip_id
    JOIN `lines` l ON l.line_id = t.line_id
    WHERE (p_line_id IS NULL OR l.line_id = p_line_id)
    GROUP BY l.line_id, l.line_name
    ORDER BY avg_delay_min DESC;
END$$
DELIMITER ;

-- =====================================================================
-- End of schema.  Now run database/seed.sql
-- =====================================================================
