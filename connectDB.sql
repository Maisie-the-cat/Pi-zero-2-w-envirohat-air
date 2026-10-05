-- MySQL/MariaDB schema for the Enviro+ Air HAT Sensor Logger
--
-- The logger appends readings and Grafana primarily queries recent rows ordered
-- by timestamp. Keep the write path light: timestamp is the only index on the
-- hot sensor_readings table. Add measurement-specific indexes only if EXPLAIN
-- shows that a real dashboard query needs one.

CREATE DATABASE IF NOT EXISTS sensor_data;
USE sensor_data;

CREATE TABLE IF NOT EXISTS sensor_readings (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    temperature FLOAT NOT NULL,
    pressure FLOAT NOT NULL,
    humidity FLOAT NOT NULL,
    light FLOAT NOT NULL,
    oxidised FLOAT NOT NULL,
    reduced FLOAT NOT NULL,
    nh3 FLOAT NOT NULL,
    pm1 FLOAT NOT NULL,
    pm25 FLOAT NOT NULL,
    pm10 FLOAT NOT NULL,
    cpu_temp FLOAT NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_sensor_readings_timestamp (timestamp)
) ENGINE=InnoDB;

-- One row per database calendar day for optional roll-up jobs and dashboards.
-- The primary key already indexes date; no duplicate date index is needed.
CREATE TABLE IF NOT EXISTS sensor_daily_stats (
    date DATE NOT NULL,
    avg_temperature FLOAT,
    min_temperature FLOAT,
    max_temperature FLOAT,
    avg_humidity FLOAT,
    min_humidity FLOAT,
    max_humidity FLOAT,
    avg_pressure FLOAT,
    min_pressure FLOAT,
    max_pressure FLOAT,
    avg_pm25 FLOAT,
    max_pm25 FLOAT,
    reading_count INT UNSIGNED NOT NULL DEFAULT 0,
    PRIMARY KEY (date)
) ENGINE=InnoDB;
