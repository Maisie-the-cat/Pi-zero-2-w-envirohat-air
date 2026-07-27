#!/usr/bin/env python3
"""
Enviro+ Air HAT Data Logger for Raspberry Pi Zero W
Logs sensor data to MySQL database continuously with async support,
connection pooling, and Prometheus metrics.
"""

import os
import time
import signal
import sys
import logging
import asyncio
import socket
from logging.handlers import RotatingFileHandler
from datetime import datetime
from dotenv import load_dotenv
from prometheus_client import start_http_server, Gauge, Counter, Info
from mysql.connector import pooling, Error

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
DEFAULT_PROMETHEUS_PORT = 8000

# Sensor value constants
DEFAULT_SENSOR_VALUE = 0.0
PMS_TIMEOUT_SECONDS = 5
SENSOR_RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 10
DB_RETRY_ATTEMPTS = 5
DB_RETRY_DELAY = 5  # seconds
CONNECTION_POOL_SIZE = 5
CONNECTION_POOL_NAME = 'sensor_pool'

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
LOG_STARTING_ASYNC = "Starting async sensor logger..."
LOG_STARTING_PROMETHEUS = "Starting Prometheus metrics server"

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


class DatabaseConfigError(ValueError):
    """Raised when database configuration is invalid"""
    pass


class SensorInitializationError(RuntimeError):
    """Raised when sensor initialization fails"""
    pass


class DatabaseConnectionError(RuntimeError):
    """Raised when database connection fails"""
    pass


# Database configuration from environment variables
def get_db_config():
    """Get and validate database configuration"""
    config = {
        'host': os.getenv('DB_HOST', DEFAULT_DB_HOST),
        'user': os.getenv('DB_USER', DEFAULT_DB_USER),
        'password': os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('DB_NAME', DEFAULT_DB_NAME),
        'pool_name': CONNECTION_POOL_NAME,
        'pool_size': int(os.getenv('CONNECTION_POOL_SIZE', str(CONNECTION_POOL_SIZE))),
        'pool_reset_session': True
    }
    
    # Validate required fields (password can be empty for password-less auth)
    required_fields = ['host', 'user', 'database']
    missing = [field for field in required_fields if not config[field]]
    
    if missing:
        logger.error(f"Missing database configuration for: {', '.join(missing)}")
        logger.error("Please set environment variables: DB_HOST, DB_USER, DB_NAME")
        raise DatabaseConfigError(f"Missing required database configuration: {', '.join(missing)}")
    
    return config


# Sensor reading interval in seconds
READING_INTERVAL = int(os.getenv('READING_INTERVAL', str(DEFAULT_READING_INTERVAL)))

# Prometheus metrics
SENSOR_READINGS_TOTAL = Counter(
    'sensor_readings_total',
    'Total number of sensor readings',
    ['sensor_type']
)
SENSOR_READINGS_SUCCESS = Counter(
    'sensor_readings_success_total',
    'Total number of successful sensor readings'
)
SENSOR_READINGS_FAILED = Counter(
    'sensor_readings_failed_total',
    'Total number of failed sensor readings'
)
DB_INSERTS_TOTAL = Counter(
    'db_inserts_total',
    'Total number of database inserts'
)
DB_INSERTS_FAILED = Counter(
    'db_inserts_failed_total',
    'Total number of failed database inserts'
)
DB_CONNECTION_RETRIES = Counter(
    'db_connection_retries_total',
    'Total number of database connection retries'
)
SENSOR_VALUE_GAUGES = {
    'temperature': Gauge('sensor_temperature_celsius', 'Temperature in °C'),
    'pressure': Gauge('sensor_pressure_hpa', 'Pressure in hPa'),
    'humidity': Gauge('sensor_humidity_percent', 'Relative humidity in %'),
    'light': Gauge('sensor_light_lux', 'Light level in lux'),
    'oxidised': Gauge('sensor_gas_oxidising', 'Oxidising gas resistance'),
    'reduced': Gauge('sensor_gas_reducing', 'Reducing gas resistance'),
    'nh3': Gauge('sensor_gas_nh3', 'NH3 gas resistance'),
    'pm1': Gauge('sensor_pm1_ugm3', 'PM1.0 concentration in µg/m³'),
    'pm25': Gauge('sensor_pm25_ugm3', 'PM2.5 concentration in µg/m³'),
    'pm10': Gauge('sensor_pm10_ugm3', 'PM10 concentration in µg/m³'),
    'cpu_temp': Gauge('sensor_cpu_temperature_celsius', 'CPU temperature in °C')
}
APP_INFO = Info('sensor_logger_info', 'Sensor Logger Application Information')
HEALTH_CHECK = Gauge('sensor_logger_health', 'Application health status (1=healthy, 0=unhealthy)')


def is_port_available(port, host='0.0.0.0'):
    """Check if a port is available"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except (OSError, socket.error):
        return False


def find_available_port(start_port, max_attempts=10):
    """Find an available port starting from start_port"""
    for i in range(max_attempts):
        port = start_port + i
        if is_port_available(port):
            return port
    return None


class EnviroSensorLogger:
    def __init__(self, use_async=False, enable_prometheus=False):
        self.db_connection = None
        self.db_pool = None
        self.batch_data = []
        self.max_batch_size = int(os.getenv('BATCH_SIZE', str(DEFAULT_BATCH_SIZE)))
        self.use_async = use_async
        self.enable_prometheus = enable_prometheus
        self.running = False
        self.sensors_initialized = False
        self.async_loop = None

        # Set application info
        APP_INFO.info({
            'version': '1.1.0',
            'use_async': str(use_async),
            'enable_prometheus': str(enable_prometheus)
        })

        # Initialize health check
        HEALTH_CHECK.set(1)

        # Register signal handlers
        signal.signal(signal.SIGTERM, self.shutdown)
        signal.signal(signal.SIGINT, self.shutdown)

    def shutdown(self, signum, frame):
        """Handle graceful shutdown"""
        logger.info(f"Received signal {signum}. Shutting down gracefully...")
        HEALTH_CHECK.set(0)
        self.running = False
        
        # Flush any remaining data
        if self.batch_data:
            logger.info(LOG_FLUSHING_DATA)
            try:
                if self.use_async and self.async_loop:
                    asyncio.run_coroutine_threadsafe(self.flush_batch_async(), self.async_loop)
                else:
                    self.flush_batch()
            except Exception as e:
                logger.error(f"Error flushing batch on shutdown: {e}")
        
        # Close database connections
        self.close_database_connections()
        
        logger.info(LOG_DB_CLOSED)
        sys.exit(0)

    def close_database_connections(self):
        """Close all database connections safely"""
        try:
            if self.db_pool:
                self.db_pool.close()
                self.db_pool = None
            elif self.db_connection and self.db_connection.is_connected():
                self.db_connection.close()
                self.db_connection = None
        except Error as e:
            logger.error(f"Error closing database connections: {e}")

    def setup_sensors(self, retry_count=0):
        """Initialize all Enviro+ Air HAT sensors"""
        if self.sensors_initialized:
            return
            
        try:
            # Import sensor libraries with fallbacks
            try:
                import bme280
                self.bme280_sensor = bme280.BME280()
            except ImportError:
                try:
                    from bme280 import BME280
                    self.bme280_sensor = BME280()
                except ImportError as e:
                    raise ImportError(f"bme280 library not found: {e}")

            # Try different PMS5003 imports
            try:
                import pms5003
                self.pms_sensor = pms5003.PMS5003()
            except ImportError:
                try:
                    from pms5003 import PMS5003
                    self.pms_sensor = PMS5003()
                except ImportError:
                    try:
                        import pimoroni_pms5003 as pms5003
                        self.pms_sensor = pms5003.PMS5003()
                    except ImportError as e:
                        raise ImportError(f"PMS5003 library not found: {e}")

            # Import gas and light sensors
            try:
                from enviroplus import gas, light
                self.gas_sensor = gas
                self.light_sensor = light
            except ImportError as e:
                raise ImportError(f"enviroplus library not found: {e}")

            self.sensors_initialized = True
            logger.info(LOG_SENSORS_INITIALIZED)

        except ImportError as e:
            logger.error(f"Sensor library import error: {e}")
            if retry_count < SENSOR_RETRY_ATTEMPTS:
                logger.info(f"Installing required libraries (attempt {retry_count + 1})...")
                self.install_sensor_libraries()
                self.setup_sensors(retry_count + 1)
            else:
                logger.critical("Failed to initialize sensors after 3 attempts. Exiting.")
                HEALTH_CHECK.set(0)
                raise SensorInitializationError("Failed to initialize sensors")

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
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', lib], 
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.info(f"Successfully installed {lib}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install {lib}: {e}")

    def setup_database(self, retry_count=0):
        """Establish database connection with pooling and retry logic"""
        try:
            DB_CONFIG = get_db_config()

            if self.use_async:
                # For async mode, use connection pooling
                self.db_pool = pooling.MySQLConnectionPool(
                    pool_name=DB_CONFIG['pool_name'],
                    pool_size=DB_CONFIG['pool_size'],
                    **{k: v for k, v in DB_CONFIG.items() if k not in ['pool_name', 'pool_size']}
                )
                self.db_connection = None
            else:
                # For sync mode, use connection pooling
                self.db_pool = pooling.MySQLConnectionPool(
                    pool_name=DB_CONFIG['pool_name'],
                    pool_size=DB_CONFIG['pool_size'],
                    **{k: v for k, v in DB_CONFIG.items() if k not in ['pool_name', 'pool_size']}
                )
                # Also keep a direct connection for compatibility
                self.db_connection = self.db_pool.get_connection()

            logger.info(LOG_DB_CONNECTED)
            self.create_table_if_not_exists()
            HEALTH_CHECK.set(1)

        except Error as e:
            logger.error(f"Database connection error (attempt {retry_count + 1}): {e}")
            DB_CONNECTION_RETRIES.inc()
            
            if retry_count < DB_RETRY_ATTEMPTS:
                delay = DB_RETRY_DELAY * (2 ** retry_count)  # Exponential backoff
                logger.info(f"Retrying database connection in {delay} seconds...")
                time.sleep(delay)
                self.setup_database(retry_count + 1)
            else:
                logger.critical(f"Failed to connect to database after {DB_RETRY_ATTEMPTS} attempts")
                HEALTH_CHECK.set(0)
                raise DatabaseConnectionError(f"Failed to connect to database: {e}")

    def get_db_connection(self):
        """Get a connection from the pool"""
        if self.db_pool:
            try:
                return self.db_pool.get_connection()
            except Error as e:
                logger.error(f"Error getting connection from pool: {e}")
                # Try to reconnect
                self.setup_database()
                return self.get_db_connection()
        elif self.db_connection and self.db_connection.is_connected():
            return self.db_connection
        else:
            self.setup_database()
            return self.get_db_connection()

    def create_table_if_not_exists(self):
        """Create sensor readings table if it doesn't exist"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
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
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_temperature (temperature),
                    INDEX idx_humidity (humidity),
                    INDEX idx_pressure (pressure)
                )
            """)
            conn.commit()
            cursor.close()
            if conn != self.db_connection:
                conn.close()
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
                    # Don't fail, just clamp to range
                    data[key] = max(min_val, min(value, max_val))

        return True

    def read_sensors(self):
        """Read all sensor data"""
        if not self.sensors_initialized:
            self.setup_sensors()
            if not self.sensors_initialized:
                logger.error("Sensors not initialized")
                SENSOR_READINGS_FAILED.inc()
                return None

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
                SENSOR_READINGS_FAILED.inc()
                return None

            # Update Prometheus gauges
            if self.enable_prometheus:
                for key, value in sensor_data.items():
                    if key in SENSOR_VALUE_GAUGES:
                        SENSOR_VALUE_GAUGES[key].set(value)
                    SENSOR_READINGS_TOTAL.labels(sensor_type=key).inc()

            SENSOR_READINGS_SUCCESS.inc()
            return sensor_data

        except Exception as e:
            logger.error(f"Error reading sensors: {e}")
            SENSOR_READINGS_FAILED.inc()
            HEALTH_CHECK.set(0)
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

        conn = None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
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
            conn.commit()
            cursor.close()

            # Update metrics
            DB_INSERTS_TOTAL.inc(len(self.batch_data))

            # Log summary
            if len(self.batch_data) > 0:
                avg_temp = sum(d['temperature'] for d in self.batch_data) / len(self.batch_data)
                logger.info(f"Logged {len(self.batch_data)} readings. Avg Temp={avg_temp:.1f}°C")

            self.batch_data = []
            return True

        except Error as e:
            logger.error(f"Batch database error: {e}")
            DB_INSERTS_FAILED.inc(len(self.batch_data))
            HEALTH_CHECK.set(0)
            if conn and conn.is_connected():
                conn.rollback()
            # Try to reconnect
            self.setup_database()
            return False
        finally:
            if conn and conn != self.db_connection:
                conn.close()

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
            DB_INSERTS_FAILED.inc()
            HEALTH_CHECK.set(0)
            self.setup_database()
            return False

    def flush_batch(self):
        """Force insert any remaining batched data"""
        if self.batch_data:
            return self._insert_batch()
        return True

    async def read_sensors_async(self):
        """Async version of read_sensors"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.read_sensors)

    async def log_to_database_async(self, sensor_data):
        """Async version of log_to_database"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.log_to_database, sensor_data)

    async def flush_batch_async(self):
        """Async version of flush_batch"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.flush_batch)

    def run(self):
        """Main loop to continuously log sensor data"""
        logger.info(LOG_STARTING_ASYNC if self.use_async else "Starting Enviro+ Air HAT sensor logger...")
        logger.info(f"Reading interval: {READING_INTERVAL} seconds")
        logger.info(f"Connection pooling: enabled with {get_db_config()['pool_size']} connections")

        # Start Prometheus server if enabled
        if self.enable_prometheus:
            prometheus_port = int(os.getenv('PROMETHEUS_PORT', str(DEFAULT_PROMETHEUS_PORT)))
            
            # Check if port is available, find alternative if not
            if not is_port_available(prometheus_port):
                logger.warning(f"Port {prometheus_port} is not available, finding alternative...")
                alt_port = find_available_port(prometheus_port)
                if alt_port:
                    prometheus_port = alt_port
                    logger.info(f"Using alternative Prometheus port: {prometheus_port}")
                else:
                    logger.error("No available port found for Prometheus, disabling metrics")
                    self.enable_prometheus = False
            
            if self.enable_prometheus:
                start_http_server(prometheus_port)
                logger.info(f"{LOG_STARTING_PROMETHEUS} on port {prometheus_port}")

        self.running = True

        try:
            if self.use_async:
                self._run_async()
            else:
                self._run_sync()
        except KeyboardInterrupt:
            pass
        finally:
            # Clean up
            self.running = False
            logger.info(LOG_FLUSHING_DATA)
            self.flush_batch()
            self.close_database_connections()
            HEALTH_CHECK.set(0)

    def _run_sync(self):
        """Synchronous main loop"""
        try:
            while self.running:
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
                    self.running = False
                    break
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    HEALTH_CHECK.set(0)
                    time.sleep(RETRY_DELAY_SECONDS)
        except KeyboardInterrupt:
            self.running = False

    def _run_async(self):
        """Asynchronous main loop"""
        async def async_loop():
            while self.running:
                try:
                    # Read sensor data asynchronously
                    sensor_data = await self.read_sensors_async()

                    # Log to database asynchronously
                    if sensor_data:
                        await self.log_to_database_async(sensor_data)

                    # Wait for next reading
                    await asyncio.sleep(READING_INTERVAL)

                except KeyboardInterrupt:
                    logger.info("Stopping async sensor logger...")
                    self.running = False
                except asyncio.CancelledError:
                    logger.info("Async loop cancelled")
                    self.running = False
                except Exception as e:
                    logger.error(f"Unexpected async error: {e}")
                    HEALTH_CHECK.set(0)
                    await asyncio.sleep(RETRY_DELAY_SECONDS)

        self.async_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.async_loop)
        
        try:
            self.async_loop.run_until_complete(async_loop())
        except KeyboardInterrupt:
            pass
        finally:
            if self.async_loop:
                self.async_loop.close()
                self.async_loop = None


def create_async_logger():
    """Factory function to create async logger with all features"""
    use_async = os.getenv('USE_ASYNC', 'false').lower() == 'true'
    enable_prometheus = os.getenv('ENABLE_PROMETHEUS', 'false').lower() == 'true'
    return EnviroSensorLogger(use_async=use_async, enable_prometheus=enable_prometheus)


if __name__ == "__main__":
    try:
        # Check if .env file exists
        if not os.path.exists('.env'):
            logger.warning(".env file not found. Using environment variables or defaults.")
            logger.warning("Create a .env file from .env.example for configuration.")
        
        sensor_logger = create_async_logger()
        sensor_logger.run()
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        HEALTH_CHECK.set(0)
        sys.exit(1)
