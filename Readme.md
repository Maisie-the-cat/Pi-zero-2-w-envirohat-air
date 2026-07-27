# Enviro+ Air HAT Sensor Logger for Raspberry Pi Zero W

A complete solution for continuously logging environmental sensor data from the Pimoroni Enviro+ Air HAT to a MySQL database, with Grafana visualization.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Hardware Requirements](#hardware-requirements)
- [Software Requirements](#software-requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Grafana Dashboard Setup](#grafana-dashboard-setup)
- [Database Schema](#database-schema)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Overview

This project provides a Python-based data logger that continuously reads environmental sensor data from the Pimoroni Enviro+ Air HAT mounted on a Raspberry Pi Zero W and stores it in a MySQL database. The collected data can be visualized using Grafana dashboards for real-time monitoring and historical analysis.

## Features

- **Continuous Monitoring**: Automatic periodic data collection from all Enviro+ sensors
- **Multiple Sensors**: Supports BME280 (temperature, pressure, humidity), gas sensors (oxidising, reducing, NH3), particulate matter sensor (PM1, PM2.5, PM10), light sensor, and CPU temperature
- **Robust Data Storage**: Reliable MySQL database storage with error handling, reconnection logic, and batch inserts
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
- Grafana

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

### 4. Install Grafana

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

# Run the logger
python3 logger.py
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
EnvironmentFile=/home/pi/Pi-zero-2-w-envirohat-air/.env
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

## Grafana Dashboard Setup

### 1. Access Grafana

Open your browser and navigate to:
```
http://your-pi-ip:3000
```

Default credentials:
- Username: `admin`
- Password: `admin`

### 2. Add MySQL Data Source

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

### 3. Create Dashboard

1. Click "+" → "Dashboard"
2. Click "Add new panel"
3. Configure panel settings:
   - Data source: `Sensor Data`
   - Query: 
     ```sql
     SELECT timestamp, temperature FROM sensor_readings ORDER BY timestamp DESC LIMIT 100
     ```
   - Visualization: Choose appropriate type (Graph, Gauge, etc.)
4. Repeat for other sensor metrics

### 4. Example Queries

**Temperature over time:**
```sql
SELECT timestamp, temperature FROM sensor_readings ORDER BY timestamp DESC LIMIT 100
```

**Humidity and Pressure:**
```sql
SELECT timestamp, humidity, pressure FROM sensor_readings ORDER BY timestamp DESC LIMIT 100
```

**Particulate Matter:**
```sql
SELECT timestamp, pm1, pm25, pm10 FROM sensor_readings ORDER BY timestamp DESC LIMIT 100
```

**All metrics:**
```sql
SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT 100
```

## Database Schema

### sensor_readings Table

| Column      | Type         | Description                    |
|-------------|--------------|--------------------------------|
| id          | INT          | Auto-increment primary key     |
| timestamp   | DATETIME     | Reading timestamp              |
| temperature | FLOAT        | Temperature in °C              |
| pressure    | FLOAT        | Pressure in hPa                |
| humidity    | FLOAT        | Relative humidity in %         |
| light       | FLOAT        | Light level (lux)              |
| oxidised    | FLOAT        | Oxidising gas resistance       |
| reduced     | FLOAT        | Reducing gas resistance        |
| nh3         | FLOAT        | NH3 gas resistance             |
| pm1         | FLOAT        | PM1.0 concentration (µg/m³)    |
| pm25        | FLOAT        | PM2.5 concentration (µg/m³)    |
| pm10        | FLOAT        | PM10 concentration (µg/m³)     |
| cpu_temp    | FLOAT        | CPU temperature in °C          |

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

3. **Permission Errors**
   - Run with appropriate user permissions
   - Check file permissions: `ls -la sensor_logger.log`
   - Ensure the user running the script has write access to the directory

4. **Grafana Not Accessible**
   - Check Grafana service: `sudo systemctl status grafana-server`
   - Verify firewall settings: `sudo ufw allow 3000`
   - Check if Grafana is listening: `ss -tulnp | grep 3000`

5. **Python Module Import Errors**
   - Ensure you're using the virtual environment: `source venv/bin/activate`
   - Reinstall dependencies: `pip install -r requirements.txt`
   - Check Python version: `python3 --version`

### Log Files

- Application logs: `sensor_logger.log` (rotated automatically)
- System logs: `journalctl -u sensor-logger.service`
- MySQL logs: `/var/log/mysql/error.log`

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
