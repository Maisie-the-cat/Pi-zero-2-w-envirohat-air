#!/usr/bin/env python3
"""
Configuration tests for Enviro+ Air HAT Sensor Logger
"""

import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPortAvailability:
    """Test port availability checking"""
    
    def test_is_port_available_used_port(self):
        """Test that a used port returns False"""
        import socket
        from logger import is_port_available
        
        # Create a socket on a random port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', 0))
            port = s.getsockname()[1]
            
            # Port should be in use
            assert not is_port_available(port)
    
    def test_is_port_available_free_port(self):
        """Test that a free port returns True"""
        from logger import is_port_available
        
        # Use a high port number that's likely free
        assert is_port_available(59999)


class TestSensorValidation:
    """Test sensor data validation"""
    
    def test_validate_sensor_data_valid(self):
        """Test validation of valid sensor data"""
        from logger import EnviroSensorLogger, SENSOR_RANGES
        
        logger = EnviroSensorLogger(use_async=False, enable_prometheus=False)
        
        # Create valid data within ranges
        valid_data = {
            'temperature': 25.0,
            'pressure': 1013.25,
            'humidity': 50.0,
            'light': 1000.0,
            'oxidised': 100000.0,
            'reduced': 100000.0,
            'nh3': 100000.0,
            'pm1': 10.0,
            'pm25': 20.0,
            'pm10': 30.0,
            'cpu_temp': 50.0
        }
        
        assert logger.validate_sensor_data(valid_data) == True
    
    def test_validate_sensor_data_out_of_range(self):
        """Test validation clamps out-of-range values"""
        from logger import EnviroSensorLogger, SENSOR_RANGES
        
        logger = EnviroSensorLogger(use_async=False, enable_prometheus=False)
        
        # Create data with out-of-range values
        invalid_data = {
            'temperature': -100.0,  # Below minimum
            'pressure': 2000.0,    # Above maximum
            'humidity': 50.0,
            'light': 1000.0,
            'oxidised': 100000.0,
            'reduced': 100000.0,
            'nh3': 100000.0,
            'pm1': 10.0,
            'pm25': 20.0,
            'pm10': 30.0,
            'cpu_temp': 50.0
        }
        
        # Should return True but clamp values
        result = logger.validate_sensor_data(invalid_data)
        assert result == True
        assert invalid_data['temperature'] == SENSOR_RANGES['temperature'][0]  # Clamped to min
        assert invalid_data['pressure'] == SENSOR_RANGES['pressure'][1]  # Clamped to max
    
    def test_validate_sensor_data_none_values(self):
        """Test validation rejects None values"""
        from logger import EnviroSensorLogger
        
        logger = EnviroSensorLogger(use_async=False, enable_prometheus=False)
        
        invalid_data = {
            'temperature': None,
            'pressure': 1013.25,
            'humidity': 50.0,
            'light': 1000.0,
            'oxidised': 100000.0,
            'reduced': 100000.0,
            'nh3': 100000.0,
            'pm1': 10.0,
            'pm25': 20.0,
            'pm10': 30.0,
            'cpu_temp': 50.0
        }
        
        assert logger.validate_sensor_data(invalid_data) == False


class TestHealthCheck:
    """Test health check functionality"""
    
    def test_health_check_initial_state(self):
        """Test that health check starts healthy"""
        from logger import HEALTH_CHECK
        
        # Reset the gauge
        HEALTH_CHECK.set(1)
        assert HEALTH_CHECK._value.get() == 1


class TestLoggerInitialization:
    """Test logger initialization"""
    
    def test_logger_creation_sync(self):
        """Test creating a sync logger"""
        from logger import EnviroSensorLogger
        
        # This should not raise any errors
        logger = EnviroSensorLogger(use_async=False, enable_prometheus=False)
        assert logger.use_async == False
        assert logger.enable_prometheus == False
        assert logger.running == False
    
    def test_logger_creation_async(self):
        """Test creating an async logger"""
        from logger import EnviroSensorLogger
        
        # This should not raise any errors
        logger = EnviroSensorLogger(use_async=True, enable_prometheus=False)
        assert logger.use_async == True
        assert logger.enable_prometheus == False
        assert logger.running == False
    
    def test_logger_creation_with_prometheus(self):
        """Test creating a logger with Prometheus enabled"""
        from logger import EnviroSensorLogger
        
        # This should not raise any errors
        logger = EnviroSensorLogger(use_async=False, enable_prometheus=True)
        assert logger.use_async == False
        assert logger.enable_prometheus == True
        assert logger.running == False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
