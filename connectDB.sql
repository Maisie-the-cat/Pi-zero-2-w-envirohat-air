-- MySQL Database Setup for Enviro+ Air HAT Sensor Logger
-- Run this script as root or with appropriate MySQL privileges

-- Create the database
CREATE DATABASE IF NOT EXISTS sensor_data;

-- Use the database
USE sensor_data;

-- Create sensor readings table with indexes for better query performance
CREATE TABLE IF NOT EXISTS sensor_readings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
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
    
    -- Indexes for better query performance
    INDEX idx_timestamp (timestamp),
    INDEX idx_temperature (temperature),
    INDEX idx_humidity (humidity),
    INDEX idx_pressure (pressure),
    INDEX idx_light (light),
    INDEX idx_pm25 (pm25),
    INDEX idx_pm10 (pm10),
    INDEX idx_cpu_temp (cpu_temp),
    
    -- Composite index for common query patterns
    INDEX idx_timestamp_temp (timestamp, temperature),
    INDEX idx_timestamp_humidity (timestamp, humidity)
);

-- Create a summary table for daily statistics (optional)
CREATE TABLE IF NOT EXISTS sensor_daily_stats (
    date DATE PRIMARY KEY,
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
    reading_count INT DEFAULT 0,
    INDEX idx_date (date)
);

-- Grant privileges to sensor user (run this as root)
-- CREATE USER 'sensor_user'@'localhost' IDENTIFIED BY 'your_secure_password';
-- GRANT ALL PRIVILEGES ON sensor_data.* TO 'sensor_user'@'localhost';
-- FLUSH PRIVILEGES;
