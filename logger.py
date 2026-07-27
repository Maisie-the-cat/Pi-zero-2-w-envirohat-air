#!/usr/bin/env python3
"""
Enviro+ Air HAT Data Logger for Raspberry Pi Zero W
Logs sensor data to MySQL database continuously
"""

import os
import time
import signal
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error

# Load environment variables
load_dotenv()

# Constants
DEFAULT_DB_HOST = 'localhost'
DEFAULT_DB_USER = 'sensor_user'
DEFAULT_DB_NAME = 'sensor_data'
DEFAULT_READING_INTERVAL = 60  # seconds
DEFAULT_BATCH_SIZE = 5
DEFAULT_LOG_LEVEL = 'INFO'
DEFAULT_LOG_MAX_BYTES = 5242880  # 5MB
DEFAULT_LOG_BACKUP_COUNT = 3

# Sensor value constants
DEFAULT_SENSOR_VALUE = 0.0
PMS_TIMEOUT_SECONDS = 5
SENSOR_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 10

# Sensor validation ranges
SENSOR_RANGES = {
    'temperature': (-50, 100),    # °C
    'pressure': (800, 1100),      # hPa
    'humidity': (0, 100),         # %
    'light': (0, 100000),        # lux
    'oxidised': (0, 1000000),    # resistance
    'reduced': (0, 1000000),     # resistance
    'nh3': (0, 1000000),         # resistance
    'pm1': (0, 1000),            # µg/m³
    'pm25': (0, 1000),           # µg/m³
    'pm10': (0, 1000),           # µg/m³
    'cpu_temp': (0, 100)         # °C
}

# Logging messages
LOG_DB_CONNECTED = "Connected to MySQL database"
LOG_SENSORS_INITIALIZED = "All sensors initialized successfully"
LOG_DB_CLOSED = "Database connection closed"
LOG_FLUSHING_DATA = "Flushing remaining data..."

# Configure logging with rotation
LOG_LEVEL = os.getenv('LOG_LEVEL', DEFAULT_LOG_LEVEL).upper()
LOG_MAX_BYTES = int(os.getenv('LOG_MAX_BYTES', str(DEFAULT_LOG_MAX_BYTES)))
LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', str(DEFAULT_LOG_BACKUP_COUNT)))

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'sensor_logger.log',
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database configuration from environment variables
DB_CONFIG = {
    'host': os.getenv('DB_HOST', DEFAULT_DB_HOST),
    'user': os.getenv('DB_USER', DEFAULT_DB_USER),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', DEFAULT_DB_NAME)
}

# Sensor reading interval in seconds
READING_INTERVAL = int(os.getenv('READING_INTERVAL', str(DEFAULT_READING_INTERVAL)))


class EnviroSensorLogger:
    def __init__(self):
        self.db_connection = None
        self.batch_data = []
        self.max_batch_size = int(os.getenv('BATCH_SIZE', str(DEFAULT_BATCH_SIZE)))
        self.setup_sensors()
        self.setup_database()
        # Register signal handlers
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

    def shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        if self.db_connection and self.db_connection.is_connected():
            try:
                if self.batch_data:
                    self._insert_batch()
                self.db_connection.close()
                logger.info(LOG_DB_CLOSED)
            except Error as e:
                logger.error(f"Error closing database connection: {e}")
        sys.exit(0)

    def setup_sensors(self, retry_count=0):
        """Initialize all Enviro+ Air HAT sensors"""
        try:
            # Import sensor libraries
            import bme280
            import pms5003
            from enviroplus import gas, light

            self.bme280_sensor = bme280.BME280()
            self.pms_sensor = pms5003.PMS5003()
            self.gas_sensor = gas
            self.light_sensor = light

            logger.info(LOG_SENSORS_INITIALIZED)

        except ImportError as e:
            logger.error(f"Sensor library import error: {e}")
            if retry_count < SENSOR_RETRY_ATTEMPTS:
                logger.info(f"Installing required libraries (attempt {retry_count + 1})...")
                self.install_sensor_libraries()
                self.setup_sensors(retry_count + 1)
            else:
                logger.critical("Failed to initialize sensors after 3 attempts. Exiting.")
                raise

    def install_sensor_libraries(self):
        """Install required sensor libraries"""
        import subprocess

        libraries = [
            'bme280',
            'pms5003',
            'enviroplus',
            'smbus2',
            'RPi.GPIO'
        ]

        for lib in libraries:
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', lib])
                logger.info(f"Successfully installed {lib}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install {lib}: {e}")

    def setup_database(self):
        """Establish database connection"""
        try:
            # Validate DB_CONFIG
            if not all(DB_CONFIG.values()):
                missing = [k for k, v in DB_CONFIG.items() if not v]
                logger.error(f"Missing database configuration for: {', '.join(missing)}")
                logger.error("Please set environment variables: DB_HOST, DB_USER, DB_PASSWORD, DB_NAME")
                raise ValueError("Incomplete database configuration")

            self.db_connection = mysql.connector.connect(**DB_CONFIG)
            if self.db_connection.is_connected():
                logger.info(LOG_DB_CONNECTED)
                self.create_table_if_not_exists()
        except Error as e:
            logger.error(f"Database connection error: {e}")
            raise

    def create_table_if_not_exists(self):
        """Create sensor readings table if it doesn't exist"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
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
                )
            """)
            self.db_connection.commit()
            cursor.close()
        except Error as e:
            logger.error(f"Error creating table: {e}")
            raise

    def validate_sensor_data(self, data):
        """Validate sensor readings before insertion"""
        if not data:
            logger.warning("No sensor data to validate")
            return False

        for key, value in data.items():
            if value is None:
                logger.warning(f"Invalid {key}: None")
                return False
            if key in SENSOR_RANGES:
                min_val, max_val = SENSOR_RANGES[key]
                if not (min_val <= value <= max_val):
                    logger.warning(f"{key} out of range: {value} (expected {min_val}-{max_val})")
                    return False

        return True

    def read_sensors(self):
        """Read all sensor data"""
        try:
            # Read BME280 (temperature, pressure, humidity)
            temperature = self.bme280_sensor.get_temperature()
            pressure = self.bme280_sensor.get_pressure()
            humidity = self.bme280_sensor.get_humidity()

            # Read light sensor
            light = self.light_sensor.read()

            # Read gas sensor
            gas_readings = self.gas_sensor.read_all()
            oxidised = gas_readings.oxidising
            reduced = gas_readings.reducing
            nh3 = gas_readings.nh3

            # Read particulate matter sensor with timeout
            try:
                self.pms_sensor.set_timeout(PMS_TIMEOUT_SECONDS)
                pm_data = self.pms_sensor.read()
                pm1 = pm_data.pm_ug_per_m3(1)
                pm25 = pm_data.pm_ug_per_m3(2.5)
                pm10 = pm_data.pm_ug_per_m3(10)
            except TimeoutError:
                logger.warning("PMS5003 read timeout, using default value")
                pm1, pm25, pm10 = DEFAULT_SENSOR_VALUE, DEFAULT_SENSOR_VALUE, DEFAULT_SENSOR_VALUE
            except Exception as e:
                logger.warning(f"PMS5003 read error: {e}, using default value")
                pm1, pm25, pm10 = DEFAULT_SENSOR_VALUE, DEFAULT_SENSOR_VALUE, DEFAULT_SENSOR_VALUE

            # Read CPU temperature
            cpu_temp = self.get_cpu_temperature()

            sensor_data = {
                'temperature': temperature,
                'pressure': pressure,
                'humidity': humidity,
                'light': light,
                'oxidised': oxidised,
                'reduced': reduced,
                'nh3': nh3,
                'pm1': pm1,
                'pm25': pm25,
                'pm10': pm10,
                'cpu_temp': cpu_temp
            }

            # Validate data
            if not self.validate_sensor_data(sensor_data):
                logger.warning("Invalid sensor data detected")
                return None

            return sensor_data

        except Exception as e:
            logger.error(f"Error reading sensors: {e}")
            return None

    def get_cpu_temperature(self):
        """Get Raspberry Pi CPU temperature"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read().strip()) / 1000.0
                return temp
        except Exception as e:
            logger.warning(f"CPU temperature read error: {e}")
            return DEFAULT_SENSOR_VALUE

    def _insert_batch(self):
        """Insert batched sensor data into database"""
        if not self.batch_data:
            return False

        try:
            cursor = self.db_connection.cursor()
            query = """
                INSERT INTO sensor_readings
                (timestamp, temperature, pressure, humidity, light, oxidised, reduced, nh3, pm1, pm25, pm10, cpu_temp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            batch_values = []
            for data in self.batch_data:
                batch_values.append((
                    datetime.now(),
                    data['temperature'],
                    data['pressure'],
                    data['humidity'],
                    data['light'],
                    data['oxidised'],
                    data['reduced'],
                    data['nh3'],
                    data['pm1'],
                    data['pm25'],
                    data['pm10'],
                    data['cpu_temp']
                ))

            cursor.executemany(query, batch_values)
            self.db_connection.commit()
            cursor.close()

            # Log summary
            if len(self.batch_data) > 0:
                avg_temp = sum(d['temperature'] for d in self.batch_data) / len(self.batch_data)
                logger.info(f"Logged {len(self.batch_data)} readings. Avg Temp={avg_temp:.1f}°C")

            self.batch_data = []
            return True

        except Error as e:
            logger.error(f"Batch database error: {e}")
            self.db_connection.rollback()
            # Try to reconnect
            self.setup_database()
            return False

    def log_to_database(self, sensor_data):
        """Log sensor data to MySQL database (with batching)"""
        if not sensor_data:
            return False

        try:
            self.batch_data.append(sensor_data)

            # Insert batch if we've reached the batch size
            if len(self.batch_data) >= self.max_batch_size:
                return self._insert_batch()

            return True

        except Error as e:
            logger.error(f"Database error: {e}")
            self.db_connection.rollback()
            # Try to reconnect
            self.setup_database()
            return False

    def flush_batch(self):
        """Force insert any remaining batched data"""
        if self.batch_data:
            return self._insert_batch()
        return True

    def run(self):
        """Main loop to continuously log sensor data"""
        logger.info("Starting Enviro+ Air HAT sensor logger...")
        logger.info(f"Reading interval: {READING_INTERVAL} seconds")

        try:
            while True:
                try:
                    # Read sensor data
                    sensor_data = self.read_sensors()

                    # Log to database
                    if sensor_data:
                        self.log_to_database(sensor_data)

                    # Wait for next reading
                    time.sleep(READING_INTERVAL)

                except KeyboardInterrupt:
                    logger.info("Stopping sensor logger...")
                    break
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    time.sleep(RETRY_DELAY_SECONDS)

        finally:
            # Clean up
            logger.info(LOG_FLUSHING_DATA)
            self.flush_batch()
            if self.db_connection and self.db_connection.is_connected():
                self.db_connection.close()
                logger.info(LOG_DB_CLOSED)


if __name__ == "__main__":
    try:
        sensor_logger = EnviroSensorLogger()
        sensor_logger.run()
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)
