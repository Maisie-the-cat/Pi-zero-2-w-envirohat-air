# Enviro+ Air HAT Sensor Logger for Raspberry Pi Zero W

A complete solution for continuously logging environmental sensor data from the Pimoroni Enviro+ Air HAT to a MySQL database, with Grafana visualization, Prometheus metrics, and async support.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Hardware Requirements](#hardware-requirements)
- [Software Requirements](#software-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Async Mode](#async-mode)
- [Prometheus Metrics](#prometheus-metrics)
- [Grafana Dashboard Setup](#grafana-dashboard-setup)
- [Database Schema](#database-schema)
- [API Endpoints](#api-endpoints)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Overview

This project provides a Python-based data logger that continuously reads environmental sensor data from the Pimoroni Enviro+ Air HAT mounted on a Raspberry Pi Zero W and stores it in a MySQL database. The collected data can be visualized using Grafana dashboards for real-time monitoring and historical analysis. Additionally, it supports Prometheus metrics for monitoring the logger itself and async operation for improved performance.

## Features

- **Continuous Monitoring**: Automatic periodic data collection from all Enviro+ sensors
- **Multiple Sensors**: Supports BME280 (temperature, pressure, humidity), gas sensors (oxidising, reducing, NH3), particulate matter sensor (PM1, PM2.5, PM10), light sensor, and CPU temperature
- **Robust Data Storage**: Reliable MySQL database storage with error handling, reconnection logic, and batch inserts
- **Connection Pooling**: Efficient database connection management with configurable pool size
- **Async Support**: Asynchronous operation for improved performance (optional)
- **Prometheus Metrics**: Built-in metrics endpoint for monitoring the logger and sensor data
- **Real-time Visualization**: Grafana integration for creating interactive dashboards
- **Comprehensive Logging**: Detailed logging to file with rotation and console output for monitoring and debugging
- **Automatic Recovery**: Handles transient errors and database disconnections gracefully
- **Configuration Management**: Environment variables for secure credential management
- **Graceful Shutdown**: Proper cleanup on SIGTERM/SIGINT signals

## Hardware Requirements

- Raspberry Pi Zero W
- Pimoroni Enviro+ Air HAT
- MicroSD card (16GB+ recommended)
- Power supply (5V/2.5A recommended)
- Optional: Case for Raspberry Pi Zero W

## Software Requirements

- Raspberry Pi OS (32-bit) with desktop
- Python 3.7+
- MySQL/MariaDB Server
- Grafana (optional, for visualization)
- Prometheus (optional, for metrics collection)

## Installation

### 1. System Setup

```bash
# Update system packages
sudo apt-get update
sudo apt-get upgrade

# Install Python and pip
sudo apt-get install python3 python3-pip python3-venv

# Install MySQL Server
sudo apt-get install mariadb-server

# Secure MySQL installation
sudo mysql_secure_installation
```

### 2. Clone Repository

```bash
git clone https://github.com/Maisie-the-cat/Pi-zero-2-w-envirohat-air.git
cd Pi-zero-2-w-envirohat-air
```

### 3. Install Python Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Install Grafana (Optional)

```bash
# Run the Grafana setup script
chmod +x Grafana.sh
./Grafana.sh
```

Or manually:

```bash
# Add Grafana repository
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -

# Install Grafana
sudo apt-get update
sudo apt-get install grafana

# Start and enable Grafana service
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

## Configuration

### 1. Database Setup

Connect to MySQL and create the database and user:

```sql
-- Login to MySQL
sudo mysql -u root -p

-- Create database
CREATE DATABASE sensor_data;

-- Create user and grant privileges
CREATE USER 'sensor_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON sensor_data.* TO 'sensor_user'@'localhost';
FLUSH PRIVILEGES;
```

### 2. Application Configuration

Copy the example environment file and edit it:

```bash
cp .env.example .env
nano .env
```

Edit the `.env` file with your configuration:

```ini
# Database Configuration
DB_HOST=localhost
DB_USER=sensor_user
DB_PASSWORD=your_secure_password
DB_NAME=sensor_data

# Sensor Configuration (in seconds)
READING_INTERVAL=60
BATCH_SIZE=5

# Connection Pooling Configuration
CONNECTION_POOL_SIZE=5
CONNECTION_POOL_NAME=sensor_pool

# Async Configuration (experimental)
USE_ASYNC=false

# Prometheus Metrics Configuration
ENABLE_PROMETHEUS=true
PROMETHEUS_PORT=8000

# Logging Configuration
LOG_LEVEL=INFO
LOG_MAX_BYTES=5242880
LOG_BACKUP_COUNT=3
```

**Important**: Never commit your `.env` file to version control. It is already excluded via `.gitignore`.

### 3. Create Database Table

The logger will automatically create the required table on first run. Alternatively, you can create it manually:

```bash
mysql -u sensor_user -p sensor_data < connectDB.sql
```

## Usage

### Running the Logger

```bash
# Activate virtual environment (if using one)
source venv/bin/activate

# Run the logger (sync mode, default)
python3 logger.py

# Run with async support
USE_ASYNC=true python3 logger.py

# Run with Prometheus metrics
ENABLE_PROMETHEUS=true python3 logger.py

# Run with both async and Prometheus
USE_ASYNC=true ENABLE_PROMETHEUS=true python3 logger.py
```

### Running as a Service (Recommended)

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/sensor-logger.service
```

Add the following content (update paths as needed):

```ini
[Unit]
Description=Enviro+ Air HAT Sensor Logger
After=network.target mysql.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Pi-zero-2-w-envirohat-air
EnvironmentFile=/etc/sensor-logger.env
ExecStart=/home/pi/Pi-zero-2-w-envirohat-air/venv/bin/python /home/pi/Pi-zero-2-w-envirohat-air/logger.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Note**: For environment variables to work with systemd, you need to:
1. Create a separate environment file (e.g., `/etc/sensor-logger.env`) with the same content as `.env`
2. Update the service file to point to it: `EnvironmentFile=/etc/sensor-logger.env`

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sensor-logger.service
sudo systemctl start sensor-logger.service
```

Check service status:

```bash
sudo systemctl status sensor-logger.service
```

View logs:

```bash
journalctl -u sensor-logger.service -f
```

## Async Mode

The logger supports asynchronous operation for improved performance. This is particularly useful when:
- Reading from multiple sensors concurrently
- Handling high-frequency data collection
- Running on multi-core systems

### Enable Async Mode

Set `USE_ASYNC=true` in your `.env` file or environment:

```bash
USE_ASYNC=true python3 logger.py
```

### Async Features

- Non-blocking sensor reads (using thread pool executor)
- Asynchronous database operations
- Improved throughput for batch operations
- Better resource utilization

**Note**: Async mode is experimental and requires Python 3.7+. The current implementation uses thread pool executors to wrap synchronous sensor libraries. Native async sensor libraries would provide better performance.

## Prometheus Metrics

The logger includes built-in Prometheus metrics for monitoring the application and sensor data.

### Enable Prometheus

Set `ENABLE_PROMETHEUS=true` in your `.env` file or environment:

```bash
ENABLE_PROMETHEUS=true python3 logger.py
```

The metrics server will start on port 8000 by default (configurable via `PROMETHEUS_PORT`).

### Available Metrics

#### Application Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `sensor_logger_info` | Info | Application version and configuration |
| `sensor_readings_total` | Counter | Total sensor readings by type |
| `sensor_readings_success_total` | Counter | Successful sensor readings |
| `sensor_readings_failed_total` | Counter | Failed sensor readings |
| `db_inserts_total` | Counter | Total database inserts |
| `db_inserts_failed_total` | Counter | Failed database inserts |

#### Sensor Value Metrics (Gauges)

| Metric | Type | Description |
|--------|------|-------------|
| `sensor_temperature_celsius` | Gauge | Current temperature in °C |
| `sensor_pressure_hpa` | Gauge | Current pressure in hPa |
| `sensor_humidity_percent` | Gauge | Current humidity in % |
| `sensor_light_lux` | Gauge | Current light level in lux |
| `sensor_gas_oxidising` | Gauge | Current oxidising gas resistance |
| `sensor_gas_reducing` | Gauge | Current reducing gas resistance |
| `sensor_gas_nh3` | Gauge | Current NH3 gas resistance |
| `sensor_pm1_ugm3` | Gauge | Current PM1.0 concentration |
| `sensor_pm25_ugm3` | Gauge | Current PM2.5 concentration |
| `sensor_pm10_ugm3` | Gauge | Current PM10 concentration |
| `sensor_cpu_temperature_celsius` | Gauge | Current CPU temperature |

### Prometheus Configuration

Add the following to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'sensor_logger'
    static_configs:
      - targets: ['localhost:8000']
    scrape_interval: 15s
```

### Example Queries

**Check logger is running:**
```promql
up{job="sensor_logger"}
```

**Get current temperature:**
```promql
sensor_temperature_celsius
```

**Sensor reading success rate:**
```promql
rate(sensor_readings_success_total[5m]) / rate(sensor_readings_total[5m])
```

**Database insert rate:**
```promql
rate(db_inserts_total[5m])
```

## Grafana Dashboard Setup

### 1. Access Grafana

Open your browser and navigate to:
```
http://your-pi-ip:3000
```

Default credentials:
- Username: `admin`
- Password: `admin`

### 2. Add Data Sources

#### MySQL Data Source (for sensor data)

1. Click on "Configuration" (gear icon) → "Data Sources"
2. Click "Add data source"
3. Select "MySQL"
4. Configure the connection:
   - Name: `Sensor Data`
   - Host: `localhost:3306`
   - Database: `sensor_data`
   - User: `sensor_user`
   - Password: `your_secure_password`
5. Click "Save & Test"

#### Prometheus Data Source (for logger metrics)

1. Click on "Configuration" (gear icon) → "Data Sources"
2. Click "Add data source"
3. Select "Prometheus"
4. Configure the connection:
   - Name: `Logger Metrics`
   - URL: `http://localhost:8000`
5. Click "Save & Test"

### 3. Create Dashboard

1. Click "+" → "Dashboard"
2. Click "Add new panel"
3. Configure panel settings:
   - Data source: `Sensor Data` (for sensor readings) or `Logger Metrics` (for application metrics)
   - Query: See example queries below
   - Visualization: Choose appropriate type (Graph, Gauge, Stat, etc.)
4. Repeat for other metrics

### 4. Example Queries

**Sensor Data (MySQL):**

Temperature over time:
```sql
SELECT timestamp, temperature FROM sensor_readings ORDER BY timestamp DESC LIMIT 100
```

Humidity and Pressure:
```sql
SELECT timestamp, humidity, pressure FROM sensor_readings ORDER BY timestamp DESC LIMIT 100
```

Particulate Matter:
```sql
SELECT timestamp, pm1, pm25, pm10 FROM sensor_readings ORDER BY timestamp DESC LIMIT 100
```

All metrics:
```sql
SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT 100
```

**Logger Metrics (Prometheus):**

Current temperature:
```promql
sensor_temperature_celsius
```

Reading success rate:
```promql
100 * (1 - (rate(sensor_readings_failed_total[5m]) / rate(sensor_readings_total[5m])))
```

Database operations:
```promql
rate(db_inserts_total[5m])
```

## Database Schema

### sensor_readings Table

| Column | Type | Description |
|--------|------|-------------|
| id | INT | Auto-increment primary key |
| timestamp | DATETIME | Reading timestamp |
| temperature | FLOAT | Temperature in °C |
| pressure | FLOAT | Pressure in hPa |
| humidity | FLOAT | Relative humidity in % |
| light | FLOAT | Light level (lux) |
| oxidised | FLOAT | Oxidising gas resistance |
| reduced | FLOAT | Reducing gas resistance |
| nh3 | FLOAT | NH3 gas resistance |
| pm1 | FLOAT | PM1.0 concentration (µg/m³) |
| pm25 | FLOAT | PM2.5 concentration (µg/m³) |
| pm10 | FLOAT | PM10 concentration (µg/m³) |
| cpu_temp | FLOAT | CPU temperature in °C |

## API Endpoints

When Prometheus metrics are enabled, the following endpoint is available:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/metrics` | GET | Prometheus metrics in text format |

### Example Usage

```bash
# Get metrics
curl http://localhost:8000/metrics

# Get specific metric
curl http://localhost:8000/metrics | grep sensor_temperature
```

## Troubleshooting

### Common Issues

1. **Sensor Not Detected**
   - Ensure Enviro+ Air HAT is properly seated
   - Check I2C is enabled: `sudo raspi-config` → Interface Options → I2C → Enable
   - Verify I2C devices: `sudo i2cdetect -y 1`
   - Ensure SPI is enabled for PMS5003: `sudo raspi-config` → Interface Options → SPI → Enable

2. **Database Connection Errors**
   - Verify MySQL service is running: `sudo systemctl status mariadb`
   - Check credentials in `.env` file
   - Ensure database and user exist
   - Test connection manually: `mysql -u sensor_user -p sensor_data`

3. **Connection Pool Errors**
   - Check pool size is not too large for your system
   - Verify MySQL max_connections setting is higher than pool size
   - Restart MySQL service: `sudo systemctl restart mariadb`

4. **Prometheus Not Accessible**
   - Check if port is in use: `ss -tulnp | grep 8000`
   - Verify firewall settings: `sudo ufw allow 8000`
   - Check if Prometheus is enabled: `ENABLE_PROMETHEUS=true`

5. **Async Mode Issues**
   - Ensure Python 3.7+ is installed
   - Try running in sync mode first: `USE_ASYNC=false`
   - Check for any blocking operations

6. **Permission Errors**
   - Run with appropriate user permissions
   - Check file permissions: `ls -la sensor_logger.log`
   - Ensure the user running the script has write access to the directory

7. **Grafana Not Accessible**
   - Check Grafana service: `sudo systemctl status grafana-server`
   - Verify firewall settings: `sudo ufw allow 3000`
   - Check if Grafana is listening: `ss -tulnp | grep 3000`

8. **Python Module Import Errors**
   - Ensure you're using the virtual environment: `source venv/bin/activate`
   - Reinstall dependencies: `pip install -r requirements.txt`
   - Check Python version: `python3 --version`

### Log Files

- Application logs: `sensor_logger.log` (rotated automatically)
- System logs: `journalctl -u sensor-logger.service`
- MySQL logs: `/var/log/mysql/error.log`
- Prometheus logs: Check the console output when starting the logger

### Debug Mode

To enable verbose logging, set `LOG_LEVEL=DEBUG` in your `.env` file and restart the logger.

## Project Structure

```
Pi-zero-2-w-envirohat-air/
├── logger.py              # Main sensor logger script
├── Grafana.sh             # Grafana installation script
├── connectDB.sql          # Database schema SQL
├── requirements.txt       # Python dependencies
├── Readme.md              # This documentation
├── LICENSE                # GPLv3 License
├── .env.example           # Example environment configuration
├── .gitignore             # Git ignore patterns
└── sensor_logger.log      # Application log file (generated)
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the GPLv3 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Pimoroni for the Enviro+ Air HAT
- Raspberry Pi Foundation
- Grafana Labs
- MySQL/MariaDB communities
- Prometheus community
