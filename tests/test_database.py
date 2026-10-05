#!/usr/bin/env python3
"""Unit tests for database operations without a live MySQL service."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from mysql.connector import Error

# Add parent directory to path for direct test execution.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sensor_logger():
    from logger import EnviroSensorLogger

    return EnviroSensorLogger(use_async=False, enable_prometheus=False)


def reading(temperature=21.5):
    return {
        'temperature': temperature,
        'pressure': 1013.25,
        'humidity': 48.0,
        'light': 120.0,
        'oxidised': 1000.0,
        'reduced': 1100.0,
        'nh3': 900.0,
        'pm1': 4.0,
        'pm25': 7.0,
        'pm10': 10.0,
        'cpu_temp': 42.0,
    }


class TestDatabaseSchema:
    """Tests for schema creation and connection cleanup."""

    def test_create_table_commits_and_closes_connection(self, sensor_logger):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        sensor_logger.db_connection = None

        with patch.object(sensor_logger, 'get_db_connection', return_value=connection):
            sensor_logger.create_table_if_not_exists()

        create_statement = cursor.execute.call_args.args[0]
        assert 'CREATE TABLE IF NOT EXISTS sensor_readings' in create_statement
        assert 'INDEX idx_timestamp (timestamp)' in create_statement
        connection.commit.assert_called_once_with()
        cursor.close.assert_called_once_with()
        connection.close.assert_called_once_with()


class TestDatabaseWrites:
    """Tests for batched, parameterized inserts and failure recovery."""

    def test_insert_batch_uses_parameterized_values_and_clears_batch(self, sensor_logger):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        sensor_logger.batch_data = [reading(), reading(22.0)]

        with patch.object(sensor_logger, 'get_db_connection', return_value=connection):
            assert sensor_logger._insert_batch() is True

        query, values = cursor.executemany.call_args.args
        assert 'INSERT INTO sensor_readings' in query
        assert query.count('%s') == 12
        assert '21.5' not in query
        assert len(values) == 2
        assert values[0][1] == 21.5
        assert values[1][1] == 22.0
        connection.commit.assert_called_once_with()
        cursor.close.assert_called_once_with()
        connection.close.assert_called_once_with()
        assert sensor_logger.batch_data == []

    def test_insert_batch_rolls_back_and_reconnects_on_database_error(self, sensor_logger):
        connection = MagicMock()
        connection.is_connected.return_value = True
        cursor = connection.cursor.return_value
        cursor.executemany.side_effect = Error('insert failed')
        sensor_logger.batch_data = [reading()]

        with patch.object(sensor_logger, 'get_db_connection', return_value=connection):
            with patch.object(sensor_logger, 'setup_database') as reconnect:
                assert sensor_logger._insert_batch() is False

        connection.rollback.assert_called_once_with()
        reconnect.assert_called_once_with()
        connection.close.assert_called_once_with()
        assert sensor_logger.batch_data == [reading()]

    def test_log_to_database_flushes_when_batch_size_is_reached(self, sensor_logger):
        sensor_logger.max_batch_size = 2

        with patch.object(sensor_logger, '_insert_batch', return_value=True) as insert_batch:
            assert sensor_logger.log_to_database(reading()) is True
            insert_batch.assert_not_called()

            assert sensor_logger.log_to_database(reading(22.0)) is True
            insert_batch.assert_called_once_with()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
