#!/bin/bash
set -e

# Enviro+ Air HAT Sensor Logger Setup Script
# This script helps set up the sensor logger on Raspberry Pi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "Enviro+ Air HAT Sensor Logger Setup"
echo "=========================================="
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "Warning: This script is designed for Raspberry Pi."
    echo "Some features may not work on other systems."
    echo ""
fi

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Warning: Running as root is not recommended."
    echo "Please run this script as a regular user (e.g., pi)."
    echo "Some commands will require sudo."
    echo ""
fi

# Step 1: Update system
echo "Step 1: Updating system packages..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# Step 2: Install dependencies
echo ""
echo "Step 2: Installing system dependencies..."
sudo apt-get install -y -qq python3 python3-pip python3-venv python3-dev libmysqlclient-dev

# Step 3: Create virtual environment
echo ""
echo "Step 3: Creating Python virtual environment..."
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    python3 -m venv "$SCRIPT_DIR/venv"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Step 4: Install Python dependencies
echo ""
echo "Step 4: Installing Python dependencies..."
source "$SCRIPT_DIR/venv/bin/activate"
pip install --upgrade pip -q
pip install -r "$SCRIPT_DIR/requirements.txt" -q

# Step 5: Create .env file
echo ""
echo "Step 5: Creating configuration file..."
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo "✓ .env file created from .env.example"
    echo "  Please edit $SCRIPT_DIR/.env with your database credentials"
else
    echo "✓ .env file already exists"
fi

# Step 6: Setup database
echo ""
echo "Step 6: Setting up database..."
read -p "Do you want to set up the MySQL database now? (y/N): " -n 1 -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    
    # Check if MySQL is installed
    if ! command -v mysql &> /dev/null; then
        echo "MySQL/MariaDB not found. Installing..."
        sudo apt-get install -y -qq mariadb-server
        sudo mysql_secure_installation
    fi
    
    # Create database
    echo "Creating database and user..."
    sudo mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS sensor_data;"
    
    # Get user input for credentials
    read -p "Enter database username [sensor_user]: " db_user
    db_user=${db_user:-sensor_user}
    
    read -s -p "Enter database password: " db_pass
    echo ""
    read -s -p "Confirm database password: " db_pass_confirm
    echo ""
    
    if [ "$db_pass" != "$db_pass_confirm" ]; then
        echo "Error: Passwords do not match!"
        exit 1
    fi
    
    if [ -n "$db_pass" ]; then
        sudo mysql -u root -p -e "CREATE USER IF NOT EXISTS '$db_user'@'localhost' IDENTIFIED BY '$db_pass';"
        sudo mysql -u root -p -e "GRANT ALL PRIVILEGES ON sensor_data.* TO '$db_user'@'localhost';"
        sudo mysql -u root -p -e "FLUSH PRIVILEGES;"
        
        # Update .env file
        sed -i "s/^DB_USER=.*/DB_USER=$db_user/" "$SCRIPT_DIR/.env"
        sed -i "s/^DB_PASSWORD=.*/DB_PASSWORD=$db_pass/" "$SCRIPT_DIR/.env"
        
        echo "✓ Database user created and privileges granted"
    else
        echo "No password provided. Using default configuration."
    fi
    
    # Import SQL schema
    echo "Importing database schema..."
    mysql -u "$db_user" -p"$db_pass" sensor_data < "$SCRIPT_DIR/connectDB.sql"
    echo "✓ Database schema imported"
else
    echo "Skipping database setup. You can set it up manually later."
fi

# Step 7: Test sensor libraries
echo ""
echo "Step 7: Testing sensor library imports..."
source "$SCRIPT_DIR/venv/bin/activate"
python3 -c "
import sys
try:
    import bme280
    print('✓ bme280 imported successfully')
except ImportError as e:
    print(f'✗ bme280 import failed: {e}')
    
try:
    import pms5003
    print('✓ pms5003 imported successfully')
except ImportError as e:
    print(f'✗ pms5003 import failed: {e}')
    
try:
    from enviroplus import gas, light
    print('✓ enviroplus imported successfully')
except ImportError as e:
    print(f'✗ enviroplus import failed: {e}')
" 2>&1

# Step 8: Setup systemd service (optional)
echo ""
echo "Step 8: Setting up systemd service (optional)..."
read -p "Do you want to set up the sensor logger as a systemd service? (y/N): " -n 1 -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    
    # Copy service file
    sudo cp "$SCRIPT_DIR/sensor-logger.service" /etc/systemd/system/
    
    # Create environment file
    echo "Creating environment file..."
    sudo cp "$SCRIPT_DIR/.env" /etc/sensor-logger.env
    sudo chmod 600 /etc/sensor-logger.env
    
    # Update service file with correct paths
    sudo sed -i "s|/home/pi/Pi-zero-2-w-envirohat-air|$SCRIPT_DIR|g" /etc/systemd/system/sensor-logger.service
    
    # Reload systemd
    sudo systemctl daemon-reload
    sudo systemctl enable sensor-logger.service
    
    echo "✓ Systemd service set up"
    echo "  Start with: sudo systemctl start sensor-logger.service"
    echo "  Check status: sudo systemctl status sensor-logger.service"
    echo "  View logs: journalctl -u sensor-logger.service -f"
else
    echo "Skipping systemd service setup."
fi

# Step 9: Final instructions
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "To start the logger manually:"
echo "  cd $SCRIPT_DIR"
echo "  source venv/bin/activate"
echo "  python3 logger.py"
echo ""
echo "To run with async mode:"
echo "  USE_ASYNC=true python3 logger.py"
echo ""
echo "To run with Prometheus metrics:"
echo "  ENABLE_PROMETHEUS=true python3 logger.py"
echo ""
echo "To run tests:"
echo "  source venv/bin/activate"
echo "  pytest tests/ -v"
echo ""
echo "For more information, see Readme.md"
echo ""
