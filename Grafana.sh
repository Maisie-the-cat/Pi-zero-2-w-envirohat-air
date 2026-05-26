# Add Grafana repository
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -

# Install Grafana
sudo apt-get update
sudo apt-get install grafana

# Start Grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server

# Install dependencies
pip3 install mysql-connector-python bme280 pms5003 enviroplus smbus2 RPi.GPIO

# Start Logging Data
chmod +x sensor_logger.py
python3 sensor_logger.py


