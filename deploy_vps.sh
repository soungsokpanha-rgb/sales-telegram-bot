#!/bin/bash
set -e

echo "====================================================="
echo "  Setting up Concept Stores Sales Bot on Ubuntu VPS  "
echo "====================================================="

# 1. Update and install dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv tzdata

# 2. Set Timezone to Asia/Phnom_Penh (GMT+7)
sudo timedatectl set-timezone Asia/Phnom_Penh
echo "Timezone configured: $(timedatectl | grep 'Time zone')"

# 3. Create Python virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# 4. Install python packages
echo "Installing Python dependencies..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# 5. Setup systemd service
SERVICE_PATH="/etc/systemd/system/salesbot.service"
CURRENT_DIR=$(pwd)

cat << EOF | sudo tee $SERVICE_PATH
[Unit]
Description=Concept Stores Telegram Sales Bot
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$CURRENT_DIR
ExecStart=$CURRENT_DIR/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 6. Enable and Start Service
echo "Enabling and starting salesbot service..."
sudo systemctl daemon-reload
sudo systemctl enable salesbot
sudo systemctl restart salesbot

echo ""
echo "====================================================="
echo "✅ Bot has been deployed and is RUNNING in background!"
echo "Check status anytime with: sudo systemctl status salesbot"
echo "View live logs with:       sudo journalctl -u salesbot -f"
echo "====================================================="
