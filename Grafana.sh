#!/bin/bash
set -euo pipefail

# Grafana Installation Script for Enviro+ Air HAT Sensor Logger
# This script installs Grafana and sets up the environment for the sensor logger

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "Grafana Installation Script"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script requires root privileges. Please run with sudo."
    exit 1
fi

# Add Grafana repository
echo "Adding Grafana repository..."
echo "deb https://packages.grafana.com/oss/deb stable main" | tee /etc/apt/sources.list.d/grafana.list > /dev/null

# Add Grafana GPG key
if ! apt-key list 2>/dev/null | grep -q "Grafana"; then
    echo "Adding Grafana GPG key..."
    wget -q -O - https://packages.grafana.com/gpg.key | apt-key add - 2>/dev/null
fi

# Update package lists
echo "Updating package lists..."
apt-get update -qq

# Install Grafana
echo "Installing Grafana..."
apt-get install -y grafana 2>/dev/null

# Start and enable Grafana service
echo "Starting Grafana service..."
systemctl daemon-reload
systemctl start grafana-server
systemctl enable grafana-server

# Verify Grafana is running
if systemctl is-active --quiet grafana-server; then
    echo "✓ Grafana service is running"
else
    echo "✗ Failed to start Grafana service"
    exit 1
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "Found requirements.txt, installing dependencies..."
    if command -v pip3 &>/dev/null; then
        pip3 install -r "$SCRIPT_DIR/requirements.txt"
    else
        echo "pip3 not found, trying pip..."
        pip install -r "$SCRIPT_DIR/requirements.txt"
    fi
else
    echo "requirements.txt not found. Installing default dependencies..."
    if command -v pip3 &>/dev/null; then
        pip3 install mysql-connector-python bme280 pms5003 enviroplus smbus2 RPi.GPIO python-dotenv prometheus-client
    else
        pip install mysql-connector-python bme280 pms5003 enviroplus smbus2 RPi.GPIO python-dotenv prometheus-client
    fi
fi

# Create .env file from example if it doesn't exist
if [ -f "$SCRIPT_DIR/.env.example" ] && [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo ""
    echo "Creating .env file from .env.example..."
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo "✓ .env file created. Please edit it with your database credentials."
    echo "  Run: nano $SCRIPT_DIR/.env"
fi

# Set proper permissions
echo ""
echo "Setting permissions..."
chmod +x "$SCRIPT_DIR/logger.py" 2>/dev/null || true

# Display completion message
echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Grafana is now installed and running."
echo "Access Grafana at: http://$(hostname -I | awk '{print $1}'):3000"
echo "Default credentials: admin/admin"
echo ""
echo "To start the sensor logger manually:"
echo "  cd $SCRIPT_DIR"
echo "  source venv/bin/activate  # If using virtual environment"
echo "  python3 logger.py"
echo ""
echo "To run as a service (recommended):"
echo "  See Readme.md for systemd service setup instructions"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your database credentials"
echo "2. Create database: mysql -u root -p < connectDB.sql"
echo "3. Start the logger service"
echo ""
