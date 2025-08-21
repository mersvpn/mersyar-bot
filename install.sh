#!/bin/bash
set -e

# --- Helper Functions for Colors ---
info() { echo -e "\e[34m[INFO]\e[0m $1"; }
success() { echo -e "\e[32m[SUCCESS]\e[0m $1"; }
error() { echo -e "\e[31m[ERROR]\e[0m $1"; }

# --- Static Configuration ---
GITHUB_USER="mersvpn"
GITHUB_REPO="mersyar-bot"

# --- Dynamic Configuration (Fetched from GitHub) ---
LATEST_TAG=$(wget -qO- "https://api.github.com/repos/$GITHUB_USER/$GITHUB_REPO/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
if [ -z "$LATEST_TAG" ]; then
    error "Could not fetch the latest release tag. Please ensure a release exists on GitHub."
    exit 1
fi
DOWNLOAD_URL="https://github.com/$GITHUB_USER/$GITHUB_REPO/archive/refs/tags/$LATEST_TAG.tar.gz"

info "==============================================="
info "      Mersyar-Bot Universal Installer"
info "==============================================="
info "Latest Version Found: $LATEST_TAG"

# --- Interactive User Input ---
read -p "Enter your Domain/Subdomain (e.g., bot.example.com): " DOMAIN
read -p "Enter your email for SSL certificate notifications: " ADMIN_EMAIL
echo "---"
read -p "Enter your Telegram Bot Token: " TELEGRAM_BOT_TOKEN
read -p "Enter the numeric Telegram Admin User ID: " AUTHORIZED_USER_IDS
read -p "Enter the Support Username (optional, press Enter to skip): " SUPPORT_USERNAME

info "✅ Configuration received. Starting the installation process..."
sleep 2

# --- Script Internal Variables ---
PROJECT_DIR="/root/$GITHUB_REPO"
SERVICE_NAME="$GITHUB_REPO"
PYTHON_ALIAS="python3"
WEBHOOK_SECRET_TOKEN="$TELEGRAM_BOT_TOKEN"
TARBALL_NAME="${LATEST_TAG}.tar.gz"
DB_NAME="mersyar_bot_db"
DB_USER="mersyar"
DB_PASSWORD=$(openssl rand -base64 16)

# 1. Update System and Install Core Dependencies
info "[1/7] Updating system and installing dependencies..."
apt-get update
apt-get install -y wget tar $PYTHON_ALIAS-pip $PYTHON_ALIAS-venv nginx mysql-server python3-certbot-nginx

# 2. Download and Extract Latest Release
info "[2/7] Downloading release $LATEST_TAG from GitHub..."
wget -q "$DOWNLOAD_URL" -O "$TARBALL_NAME"

rm -rf "$PROJECT_DIR"
tar -xzf "$TARBALL_NAME"
EXTRACTED_FOLDER_NAME=$(tar -tzf "$TARBALL_NAME" | head -1 | cut -f1 -d"/")
if [ -z "$EXTRACTED_FOLDER_NAME" ]; then
    error "Could not determine the extracted folder name from the tarball."
    exit 1
fi
mv "$EXTRACTED_FOLDER_NAME" "$PROJECT_DIR"
cd "$PROJECT_DIR"
rm -f "/root/$TARBALL_NAME"

# --- FIX: Run MySQL commands with sudo to avoid access denied errors ---
info "[3/7] Setting up MySQL Database and User..."
sudo mysql -e "CREATE DATABASE IF NOT EXISTS $DB_NAME;"
sudo mysql -e "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';"
sudo mysql -e "GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"
success "MySQL database '$DB_NAME' and user '$DB_USER' created."

# 4. Create .env file with provided credentials
info "[4/7] Creating .env file..."
cat << EOF > .env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN"
AUTHORIZED_USER_IDS="$AUTHORIZED_USER_IDS"
SUPPORT_USERNAME="$SUPPORT_USERNAME"

# Webhook Configuration
WEBHOOK_SECRET_TOKEN="$WEBHOOK_SECRET_TOKEN"
BOT_DOMAIN="$DOMAIN"

# Database credentials
DB_HOST=localhost
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
EOF

# 5. Setup Python Virtual Environment and Install Requirements
info "[5/7] Setting up Python virtual environment..."
$PYTHON_ALIAS -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 6. Configure Nginx and Obtain SSL Certificate
info "[6/7] Configuring Nginx and obtaining SSL certificate..."
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

# 7. Create and Enable systemd Service
info "[7/7] Creating and enabling systemd service..."
cat << EOF > /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=$SERVICE_NAME Telegram Bot Service
After=network.target mysql.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/bot.py
Restart=on-failure
RestartSec=10
KillMode=process

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

success "==============================================="
success "✅✅✅ Installation Complete! ✅✅✅"
success "The bot (version $LATEST_TAG) is now running on https://$DOMAIN"
success "Database password (saved in .env): $DB_PASSWORD"
info "To check the service status, use: systemctl status $SERVICE_NAME"