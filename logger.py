#!/usr/bin/env python3
"""
Enviro+ Air HAT Data Logger for Raspberry Pi Zero W
Logs sensor data to MySQL database continuously
"""

import time
import mysql.connector
from mysql.connector import Error
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sensor_logger.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'your_mysql_username',
    'password': 'your_mysql_password',
    'database': 'sensor_data'
}

# Sensor reading interval in seconds
READING_INTERVAL = 60  # 1 minute

class EnviroSensorLogger:
    def __init__(self):
        self.db_connection = None
        self.setup_sensors()
        self.setup_database()
    
    def setup_sensors(self):
        """Initialize all Enviro+ Air HAT sensors"""
        try:
            # Import sensor libraries
            import bme280
            import pms5003
            import enviroplus
            from enviroplus import gas
            
            self.bme280_sensor = bme280.BME280()
            self.pms_sensor = pms5003.PMS5003()
            self.gas_sensor = gas
            
            logger.info("All sensors initialized successfully")
            
        except ImportError as e:
            logger.error(f"Sensor library import error: {e}")
            logger.info("Installing required libraries...")
            self.install_sensor_libraries()
            self.setup_sensors()
    
    def install_sensor_libraries(self):
        """Install required sensor libraries"""
        import subprocess
        import sys
        
        libraries = [
            'bme280',
            'pms5003',
            'enviroplus',
            'smbus2',
            'RPi.GPIO'
        ]
        
        for lib in libraries:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', lib])
    
    def setup_database(self):
        """Establish database connection"""
        try:
            self.db_connection = mysql.connector.connect(**DB_CONFIG)
            if self.db_connection.is_connected():
                logger.info("Connected to MySQL database")
                self.create_table_if_not_exists()
        except Error as e:
            logger.error(f"Database connection error: {e}")
            raise
    
    def create_table_if_not_exists(self):
        """Create sensor readings table if it doesn't exist"""
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
    
    def read_sensors(self):
        """Read all sensor data"""
        try:
            # Read BME280 (temperature, pressure, humidity)
            temperature = self.bme280_sensor.get_temperature()
            pressure = self.bme280_sensor.get_pressure()
            humidity = self.bme280_sensor.get_humidity()
            
            # Read light sensor
            light = self.read_light_sensor()
            
            # Read gas sensor
            gas_readings = self.gas_sensor.read_all()
            oxidised = gas_readings.oxidising
            reduced = gas_readings.reducing
            nh3 = gas_readings.nh3
            
            # Read particulate matter sensor
            pm_data = self.pms_sensor.read()
            pm1 = pm_data.pm_ug_per_m3(1)
            pm25 = pm_data.pm_ug_per_m3(2.5)
            pm10 = pm_data.pm_ug_per_m3(10)
            
            # Read CPU temperature
            cpu_temp = self.get_cpu_temperature()
            
            return {
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
            
        except Exception as e:
            logger.error(f"Error reading sensors: {e}")
            return None
    
    def read_light_sensor(self):
        """Read light sensor value"""
        try:
            # This depends on your specific light sensor implementation
            # For Enviro+ HAT, you might need to use ADC
            import smbus2
            bus = smbus2.SMBus(1)
            # Read from light sensor (address and register may vary)
            # This is a placeholder - adjust based on your hardware
            return 0.0
        except Exception as e:
            logger.warning(f"Light sensor read error: {e}")
            return 0.0
    
    def get_cpu_temperature(self):
        """Get Raspberry Pi CPU temperature"""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp = float(f.read().strip()) / 1000.0
                return temp
        except Exception as e:
            logger.warning(f"CPU temperature read error: {e}")
            return 0.0
    
    def log_to_database(self, sensor_data):
        """Log sensor data to MySQL database"""
        if not sensor_data:
            return False
        
        try:
            cursor = self.db_connection.cursor()
            query = """
                INSERT INTO sensor_readings 
                (temperature, pressure, humidity, light, oxidised, reduced, nh3, pm1, pm25, pm10, cpu_temp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                sensor_data['temperature'],
                sensor_data['pressure'],
                sensor_data['humidity'],
                sensor_data['light'],
                sensor_data['oxidised'],
                sensor_data['reduced'],
                sensor_data['nh3'],
                sensor_data['pm1'],
                sensor_data['pm25'],
                sensor_data['pm10'],
                sensor_data['cpu_temp']
            )
            
            cursor.execute(query, values)
            self.db_connection.commit()
            cursor.close()
            
            logger.info(f"Logged sensor data: Temp={sensor_data['temperature']:.1f}°C, "
                       f"Humidity={sensor_data['humidity']:.1f}%, "
                       f"Pressure={sensor_data['pressure']:.1f}hPa")
            return True
            
        except Error as e:
            logger.error(f"Database error: {e}")
            # Try to reconnect
            self.setup_database()
            return False
    
    def run(self):
        """Main loop to continuously log sensor data"""
        logger.info("Starting Enviro+ Air HAT sensor logger...")
        
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
                time.sleep(10)  # Wait before retrying
        
        # Clean up
        if self.db_connection and self.db_connection.is_connected():
            self.db_connection.close()
            logger.info("Database connection closed")

if __name__ == "__main__":
    logger = EnviroSensorLogger()
    logger.run()
