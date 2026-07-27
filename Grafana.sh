#!/bin/bash
set -euo pipefail

# Add Grafana repository
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -

# Install Grafana
sudo apt-get update
sudo apt-get install -y grafana

# Start Grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server

# Install Python dependencies
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies from requirements.txt..."
    pip3 install -r requirements.txt
else
    echo "requirements.txt not found. Installing default dependencies..."
    pip3 install mysql-connector-python bme280 pms5003 enviroplus smbus2 RPi.GPIO python-dotenv
fi

# Start Logging Data
if [ -f "logger.py" ]; then
    chmod +x logger.py
    echo "Starting logger.py..."
    python3 logger.py
else
    echo "Error: logger.py not found!"
    exit 1
fi
