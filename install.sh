#!/bin/bash
set -e

# --- Static Configuration ---
GITHUB_USER="mersvpn"
GITHUB_REPO="mersyar-bot"

# --- Dynamic Configuration (Fetched from GitHub) ---
LATEST_TAG=$(wget -qO- "https://api.github.com/repos/$GITHUB_USER/$GITHUB_REPO/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
if [ -z "$LATEST_TAG" ]; then
    echo "Error: Could not fetch the latest release tag. Please ensure a release exists on GitHub."
    exit 1
fi
DOWNLOAD_URL="https://github.com/$GITHUB_USER/$GITHUB_REPO/archive/refs/tags/$LATEST_TAG.tar.gz"

echo "==============================================="
echo "      Mersyar-Bot Universal Installer"
echo "==============================================="
echo "Latest Version Found: $LATEST_TAG"
echo "Please provide the following details:"
echo ""

# --- Interactive User Input ---
read -p "Enter your Domain/Subdomain (e.g., bot.example.com): " DOMAIN
read -p "Enter your email for SSL certificate notifications: " ADMIN_EMAIL
echo "---"
read -p "Enter your Telegram Bot Token: " TELEGRAM_BOT_TOKEN
read -p "Enter the numeric Telegram Admin User ID: " AUTHORIZED_USER_IDS
read -p "Enter the Support Username (optional, press Enter to skip): " SUPPORT_USERNAME

echo ""
echo "✅ Configuration received. Starting the installation process..."
sleep 2

# --- Script Internal Variables ---
PROJECT_DIR="/root/$GITHUB_REPO"
SERVICE_NAME="$GITHUB_REPO"
PYTHON_ALIAS="python3"
WEBHOOK_SECRET_TOKEN=$(head /dev/urandom | tr -dc A-Za-z0-9 | head -c 32)
TARBALL_NAME="${LATEST_TAG}.tar.gz"

# 1. Update System and Install Core Dependencies
echo ">>> [1/6] Updating system and installing dependencies..."
apt-get update
apt-get install -y wget tar $PYTHON_ALIAS-pip $PYTHON_ALIAS-venv nginx python3-certbot-nginx

# 2. Download and Extract Latest Release (Smart Extraction)
echo ">>> [2/6] Downloading release $LATEST_TAG from GitHub..."
wget -q "$DOWNLOAD_URL" -O "$TARBALL_NAME"

rm -rf "$PROJECT_DIR"
tar -xzf "$TARBALL_NAME"

EXTRACTED_FOLDER_NAME=$(tar -tzf "$TARBALL_NAME" | head -1 | cut -f1 -d"/")
if [ -z "$EXTRACTED_FOLDER_NAME" ]; then
    echo "Error: Could not determine the extracted folder name from the tarball."
    exit 1
fi
echo "Extracted folder identified as: $EXTRACTED_FOLDER_NAME"
mv "$EXTRACTED_FOLDER_NAME" "$PROJECT_DIR"

cd "$PROJECT_DIR"
rm -f "/root/$TARBALL_NAME"

# 3. Create .env file with provided credentials
echo ">>> [3/6] Creating .env file..."
cat << EOF > .env
TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN"
AUTHORIZED_USER_IDS="$AUTHORIZED_USER_IDS"
SUPPORT_USERNAME="$SUPPORT_USERNAME"
WEBHOOK_SECRET_TOKEN="$WEBHOOK_SECRET_TOKEN"
BOT_DOMAIN="$DOMAIN"
EOF

# 4. Setup Python Virtual Environment and Install Requirements
echo ">>> [4/6] Setting up Python virtual environment..."
$PYTHON_ALIAS -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 5. Configure Nginx and Obtain SSL Certificate
echo ">>> [5/6] Configuring Nginx and obtaining SSL certificate..."
cat << EOF > /etc/nginx/sites-available/$SERVICE_NAME
server {
    listen 80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF
ln -s -f /etc/nginx/sites-available/$SERVICE_NAME /etc/nginx/sites-enabled/
systemctl restart nginx
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email "$ADMIN_EMAIL" --redirect

# 6. Create and Enable systemd Service
echo ">>> [6/6] Creating and enabling systemd service..."
cat << EOF > /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=$SERVICE_NAME Telegram Bot Service
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/bot.py
Restart=always
RestartSec=10
KillMode=process

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

echo ""
echo "✅✅✅ Installation Complete! ✅✅✅"
echo "The bot (version $LATEST_TAG) is now running on https://$DOMAIN"
echo "To check the service status, use: systemctl status $SERVICE_NAME"