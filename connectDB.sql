-- Connect to MySQL and run these commands
CREATE DATABASE sensor_data;
USE sensor_data;

CREATE TABLE sensor_readings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    temperature FLOAT,
    pressure FLOAT,
    humidity FLOAT,
    light FLOAT,
    oxidised FLOAT,
    reduced FLOAT,
    nh3 FLOAT,
    pm1 FLOAT,
    pm25 FLOAT,
    pm10 FLOAT,
    cpu_temp FLOAT,
    INDEX idx_timestamp (timestamp)
);
