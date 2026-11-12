#!/bin/bash
set -euo pipefail

# Grafana Installation Script for Enviro+ Air HAT Sensor Logger
# This script installs Grafana and sets up the environment for the sensor logger

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APT_KEYRING="/etc/apt/keyrings/grafana.asc"
VENV_DIR="$SCRIPT_DIR/venv"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script requires root privileges. Please run with sudo."
    exit 1
fi

echo "=========================================="
echo "Grafana Installation Script"
echo "=========================================="

# Add Grafana repository
printf '%s\n' "Adding Grafana repository..."
apt-get install -y -qq apt-transport-https ca-certificates wget gnupg python3 python3-venv
install -d -m 0755 /etc/apt/keyrings

# Add Grafana's official signing key to a dedicated keyring. APT verifies
# package signatures against this keyring via the signed-by repository option.
if [ ! -s "$APT_KEYRING" ]; then
    printf '%s\n' "Adding Grafana GPG key..."
    tmp_key="$(mktemp)"
    trap 'rm -f -- "$tmp_key"' EXIT
    wget --https-only --timeout=30 --tries=3 --quiet \
        --output-document="$tmp_key" https://apt.grafana.com/gpg-full.key
    install -m 0644 "$tmp_key" "$APT_KEYRING"
    rm -f -- "$tmp_key"
    trap - EXIT
fi
printf 'deb [signed-by=%s] https://apt.grafana.com stable main\n' "$APT_KEYRING" \
    > /etc/apt/sources.list.d/grafana.list

# Update package lists
printf '%s\n' "Updating package lists..."
apt-get update -qq

# Install Grafana
printf '%s\n' "Installing Grafana..."
apt-get install -y grafana 2>/dev/null

# Start and enable Grafana service
printf '%s\n' "Starting Grafana service..."
systemctl daemon-reload
systemctl start grafana-server
systemctl enable grafana-server

# Verify Grafana is running
if systemctl is-active --quiet grafana-server; then
    printf '%s\n' "✓ Grafana service is running"
else
    printf '%s\n' "✗ Failed to start Grafana service"
    exit 1
fi

# Install the pinned Python dependencies in the project virtual environment.
printf '%s\n' "Installing Python dependencies..."
if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
    printf '%s\n' "requirements.txt is required for a pinned installation." >&2
    exit 1
fi
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --upgrade --only-binary=:all: pip -q
"$VENV_DIR/bin/python" -m pip install -r "$SCRIPT_DIR/requirements.txt" -q

# Create .env file from example if it doesn't exist
if [ -f "$SCRIPT_DIR/.env.example" ] && [ ! -f "$SCRIPT_DIR/.env" ]; then
    printf '%s\n' "Creating .env file from example..."
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    chmod 600 "$SCRIPT_DIR/.env"
    printf '%s\n' "✓ .env file created. Please edit it with your database credentials."
    printf '  Run: nano %s\n' "$SCRIPT_DIR/.env"
fi

# Set proper permissions
printf '%s\n' "Setting permissions..."
chmod +x "$SCRIPT_DIR/logger.py" 2>/dev/null || true

# Display completion message
printf '%s\n' ""
printf '%s\n' "=========================================="
printf '%s\n' "Installation Complete!"
printf '%s\n' "=========================================="
printf '%s\n' ""
printf '%s\n' "Grafana is now installed and running. Set a unique admin password on first login."
printf 'Access Grafana at: http://%s:3000\n' "$(hostname -I | awk '{print $1}')"
printf '%s\n' ""
printf '%s\n' "To start the sensor logger manually:"
printf '  cd %s\n' "$SCRIPT_DIR"
printf '%s\n' "  source venv/bin/activate"
printf '%s\n' "  python logger.py"
printf '%s\n' ""
printf '%s\n' "To run as a service (recommended):"
printf '%s\n' "  See Readme.md for systemd service setup instructions"
printf '%s\n' ""
printf '%s\n' "Next steps:"
printf '%s\n' "1. Edit .env file with your database credentials"
printf '%s\n' "2. Create database: mysql -u root -p < connectDB.sql"
printf '%s\n' "3. Start the logger service"
printf '%s\n' ""
