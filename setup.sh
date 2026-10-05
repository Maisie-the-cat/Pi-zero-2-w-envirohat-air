#!/bin/bash
set -euo pipefail

# Enviro+ Air HAT Sensor Logger Setup Script
# This script helps set up the sensor logger on Raspberry Pi.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
SCHEMA_FILE="$SCRIPT_DIR/connectDB.sql"
DB_NAME="sensor_data"
DB_HOST="localhost"
DB_PORT="3306"

cleanup_temp_files() {
    if [[ -n "${ROOT_SQL_FILE:-}" && -f "$ROOT_SQL_FILE" ]]; then
        rm -f -- "$ROOT_SQL_FILE"
    fi
    if [[ -n "${CLIENT_CNF_FILE:-}" && -f "$CLIENT_CNF_FILE" ]]; then
        rm -f -- "$CLIENT_CNF_FILE"
    fi
}
trap cleanup_temp_files EXIT

write_env_value() {
    local key="$1"
    local value="$2"
    local file="$3"
    local temp_file

    temp_file="$(mktemp "${file}.XXXXXX")"
    chmod 600 "$temp_file"

    DB_ENV_KEY="$key" DB_ENV_VALUE="$value" python3 - "$file" "$temp_file" <<'PY'
import os
import sys

source_path, target_path = sys.argv[1:]
key = os.environ["DB_ENV_KEY"]
value = os.environ["DB_ENV_VALUE"]

try:
    with open(source_path, "r", encoding="utf-8") as source:
        lines = source.readlines()
except FileNotFoundError:
    lines = []

replacement = f"{key}={value}\n"
found = False
updated = []
for line in lines:
    if line.startswith(f"{key}="):
        if not found:
            updated.append(replacement)
            found = True
    else:
        updated.append(line)

if not found:
    if updated and not updated[-1].endswith("\n"):
        updated.append("\n")
    updated.append(replacement)

with open(target_path, "w", encoding="utf-8") as target:
    target.writelines(updated)
os.replace(target_path, source_path)
PY
}

validate_db_user() {
    local user="$1"
    if [[ ! "$user" =~ ^[A-Za-z0-9_]{1,32}$ ]]; then
        echo "Error: database username must contain only letters, numbers, and underscores (max 32 characters)." >&2
        exit 1
    fi
}

# SQL string literals are escaped while NO_BACKSLASH_ESCAPES is active. This
# makes a single quote data rather than executable SQL, including in passwords.
escape_sql_literal() {
    printf '%s' "$1" | sed "s/'/''/g"
}

echo "=========================================="
echo "Enviro+ Air HAT Sensor Logger Setup"
echo "=========================================="
echo

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
    echo "Warning: This script is designed for Raspberry Pi."
    echo "Some features may not work on other systems."
    echo
fi

# Check if running as root
if [[ "$EUID" -eq 0 ]]; then
    echo "Warning: Running as root is not recommended."
    echo "Please run this script as a regular user (for example, pi)."
    echo "Some commands will require sudo."
    echo
fi

# Step 1: Update system
echo "Step 1: Updating system packages..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# Step 2: Install dependencies
echo
echo "Step 2: Installing system dependencies..."
sudo apt-get install -y -qq python3 python3-pip python3-venv python3-dev libmysqlclient-dev

# Step 3: Create virtual environment
echo
echo "Step 3: Creating Python virtual environment..."
if [[ ! -d "$SCRIPT_DIR/venv" ]]; then
    python3 -m venv "$SCRIPT_DIR/venv"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Step 4: Install Python dependencies
echo
echo "Step 4: Installing Python dependencies..."
source "$SCRIPT_DIR/venv/bin/activate"
python -m pip install --upgrade pip -q
python -m pip install -r "$SCRIPT_DIR/requirements.txt" -q

# Step 5: Create .env file
echo
echo "Step 5: Creating configuration file..."
if [[ ! -f "$ENV_FILE" ]]; then
    cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "✓ .env file created from .env.example"
    echo "  Please edit $ENV_FILE with your database credentials"
else
    chmod 600 "$ENV_FILE"
    echo "✓ .env file already exists"
fi

# Step 6: Setup database
echo
echo "Step 6: Setting up database..."
read -r -p "Do you want to set up the MySQL database now? (y/N): " -n 1 setup_database
printf '\n'
if [[ "$setup_database" =~ ^[Yy]$ ]]; then
    if ! command -v mysql >/dev/null 2>&1; then
        echo "MySQL/MariaDB not found. Installing..."
        sudo apt-get install -y -qq mariadb-server
        sudo mysql_secure_installation
    fi

    read -r -p "Enter database username [sensor_user]: " db_user
    db_user="${db_user:-sensor_user}"
    validate_db_user "$db_user"

    read -r -s -p "Enter database password: " db_pass
    printf '\n'
    read -r -s -p "Confirm database password: " db_pass_confirm
    printf '\n'

    if [[ "$db_pass" != "$db_pass_confirm" ]]; then
        echo "Error: Passwords do not match!" >&2
        exit 1
    fi

    escaped_db_pass="$(escape_sql_literal "$db_pass")"
    ROOT_SQL_FILE="$(mktemp)"
    chmod 600 "$ROOT_SQL_FILE"

    # Keep credentials out of shell command arguments. The temporary SQL file
    # is mode 600 and is removed by the EXIT trap.
    cat > "$ROOT_SQL_FILE" <<SQL
SET SESSION sql_mode = 'NO_BACKSLASH_ESCAPES';
CREATE DATABASE IF NOT EXISTS \`$DB_NAME\`;
CREATE USER IF NOT EXISTS '$db_user'@'$DB_HOST' IDENTIFIED BY '$escaped_db_pass';
ALTER USER '$db_user'@'$DB_HOST' IDENTIFIED BY '$escaped_db_pass';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER ON \`$DB_NAME\`.* TO '$db_user'@'$DB_HOST';
FLUSH PRIVILEGES;
SQL

    echo "Creating database and user..."
    sudo mysql -u root -p < "$ROOT_SQL_FILE"

    # Update .env without sed interpolation. Values are passed as data to
    # Python, so quotes, dollar signs, backslashes, and ampersands are safe.
    write_env_value "DB_HOST" "$DB_HOST" "$ENV_FILE"
    write_env_value "DB_PORT" "$DB_PORT" "$ENV_FILE"
    write_env_value "DB_USER" "$db_user" "$ENV_FILE"
    write_env_value "DB_PASSWORD" "$db_pass" "$ENV_FILE"
    write_env_value "DB_NAME" "$DB_NAME" "$ENV_FILE"

    # Avoid putting the database password in the mysql process arguments while
    # importing the schema.
    CLIENT_CNF_FILE="$(mktemp)"
    chmod 600 "$CLIENT_CNF_FILE"
    cat > "$CLIENT_CNF_FILE" <<CNF
[client]
host=$DB_HOST
port=$DB_PORT
user=$db_user
password=$db_pass
database=$DB_NAME
CNF

    echo "Importing database schema..."
    mysql --defaults-extra-file="$CLIENT_CNF_FILE" < "$SCHEMA_FILE"
    echo "✓ Database and schema configured"
else
    echo "Skipping database setup. You can set it up manually later."
fi

# Step 7: Test sensor libraries
echo
echo "Step 7: Testing sensor library imports..."
source "$SCRIPT_DIR/venv/bin/activate"
python -c "
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
"

# Step 8: Setup systemd service (optional)
echo
echo "Step 8: Setting up systemd service (optional)..."
read -r -p "Do you want to set up the sensor logger as a systemd service? (y/N): " -n 1 setup_service
printf '\n'
if [[ "$setup_service" =~ ^[Yy]$ ]]; then
    sudo cp "$SCRIPT_DIR/sensor-logger.service" /etc/systemd/system/
    echo "Creating environment file..."
    sudo cp "$ENV_FILE" /etc/sensor-logger.env
    sudo chmod 600 /etc/sensor-logger.env
    sudo sed -i "s|/home/pi/Pi-zero-2-w-envirohat-air|$SCRIPT_DIR|g" /etc/systemd/system/sensor-logger.service
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
echo
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo
echo "To start the logger manually:"
echo "  cd $SCRIPT_DIR"
echo "  source venv/bin/activate"
echo "  python logger.py"
echo
echo "To run with async mode:"
echo "  USE_ASYNC=true python logger.py"
echo
echo "To run with Prometheus metrics:"
echo "  ENABLE_PROMETHEUS=true python logger.py"
echo
echo "To run tests:"
echo "  source venv/bin/activate"
echo "  python -m pytest tests/ -v"
echo
echo "For more information, see Readme.md"
echo
