#!/bin/bash
# Sofascore Monitor - Native Systemd Deployment Script
# Run this on the Linux Laptop (Target)

set -e

# Configuration
USER="carlscamt"
PROJECT_DIR="/home/$USER/antigravity/sofascore-leaderboard-watcher"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_FILE="/etc/systemd/system/sofascore-monitor.service"

echo "🚀 Starting Native Systemd Deployment..."

# 1. Dependency Check
echo "📦 Installing System Dependencies..."
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git

# 2. Project Setup
echo "📂 Verifying Project Structure..."
mkdir -p "$PROJECT_DIR/data" "$PROJECT_DIR/logs"

# 3. Virtual Environment
if [ ! -d "$VENV_DIR" ]; then
    echo "🐍 Creating Virtual Environment..."
    python3.11 -m venv "$VENV_DIR"
fi

echo "📦 Installing Python Dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"

# 4. Environment Variables
echo "⚙️  Configuring Environment..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "⚠️  .env file not found! creating template..."
    cat > "$PROJECT_DIR/.env" <<EOF
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK
SCAN_INTERVAL_MINUTES=5
MIN_ROI=5.0
MIN_AVG_ODDS=1.5
MIN_TOTAL_BETS=10
DB_PATH=$PROJECT_DIR/data/sofascore.db
LOG_LEVEL=INFO
EOF
    echo "❗ PLEASE EDIT .env WITH REAL VALUES"
fi

# 5. Database Init
echo "Floppy Disk Initializing Database..."
python3 -c "
import sys
sys.path.insert(0, '$PROJECT_DIR/src')
from sofascore_monitor.storage import StorageLayer
storage = StorageLayer()
storage.initialize()
print('✅ Database initialized with WAL mode')
"

# 6. Systemd Service
echo "Systemd Creating Service File..."
cat <<EOF | sudo tee "$SERVICE_FILE"
[Unit]
Description=Sofascore Leaderboard Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$PROJECT_DIR

# Environment
Environment="PYTHONUNBUFFERED=1"
Environment="PYTHONPATH=$PROJECT_DIR/src"
Environment="TZ=Europe/London"
EnvironmentFile=$PROJECT_DIR/.env

# Execution
ExecStart=$VENV_DIR/bin/python main.py

# Restart policy
Restart=on-failure
RestartSec=60
StartLimitBurst=5
StartLimitIntervalSec=600

# Resource limits
MemoryMax=400M
MemoryHigh=350M
CPUQuota=40%
TasksMax=50

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=$PROJECT_DIR/data
ReadWritePaths=$PROJECT_DIR/logs

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sofascore-monitor

[Install]
WantedBy=multi-user.target
EOF

# 7. Enable & Start
echo "🔥 Enabling Service..."
sudo systemctl daemon-reload
sudo systemctl enable sofascore-monitor.service
sudo systemctl restart sofascore-monitor.service

echo "✅ Deployment Complete!"
echo "   Status: sudo systemctl status sofascore-monitor.service"
echo "   Logs:   sudo journalctl -u sofascore-monitor.service -f"
