#!/bin/bash
# Install ICAP daemon as a system service

set -e

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

# Configuration variables
INSTALL_DIR="/opt/icap"
CONFIG_DIR="/etc/icap"
DATA_DIR="/var/lib/icap"
LOG_DIR="/var/log/icap"
RUN_DIR="/run/icap"
SERVICE_NAME="icap"
USER="icap"
GROUP="icap"

# Create directories
echo "Creating directories..."
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$DATA_DIR/queue" "$LOG_DIR" "$RUN_DIR"

# Create user and group if they don't exist
if ! getent group "$GROUP" > /dev/null; then
  echo "Creating group: $GROUP"
  groupadd "$GROUP"
fi

if ! getent passwd "$USER" > /dev/null; then
  echo "Creating user: $USER"
  useradd -r -g "$GROUP" -d "$INSTALL_DIR" -s /bin/false "$USER"
fi

# Set ownership and permissions
echo "Setting permissions..."
chown -R "$USER:$GROUP" "$INSTALL_DIR" "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR" "$RUN_DIR"
chmod 750 "$INSTALL_DIR" "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR" "$RUN_DIR"

# Check if we're installing from the project directory
PROJECT_DIR=$(pwd)
if [ -f "$PROJECT_DIR/scripts/icap_daemon.py" ]; then
  echo "Installing from project directory: $PROJECT_DIR"
  
  # Copy files to installation directory
  echo "Copying files to $INSTALL_DIR..."
  rsync -av --exclude='.git' --exclude='venv' --exclude='__pycache__' "$PROJECT_DIR/" "$INSTALL_DIR/"
  
  # Create virtual environment if it doesn't exist
  if [ ! -d "$INSTALL_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$INSTALL_DIR/venv"
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/docker/processing/requirements.txt"
  fi
  
  # Install systemd service
  echo "Installing systemd service..."
  cp "$INSTALL_DIR/scripts/icap.service" /etc/systemd/system/
  systemctl daemon-reload
  
  echo "Enabling service to start on boot..."
  systemctl enable "$SERVICE_NAME"
  
  echo "Service installed. Start it with: systemctl start $SERVICE_NAME"
else
  echo "Error: Not running from project directory"
  exit 1
fi

echo "Installation complete!"