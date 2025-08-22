#!/bin/bash
set -e

# --- Helper Functions for Colors ---
info() { echo -e "\e[34m[INFO]\e[0m $1"; }
success() { echo -e "\e[32m[SUCCESS]\e[0m $1"; }
error() { echo -e "\e[31m[ERROR]\e[0m $1"; }

# --- Pre-flight Checks ---
if [ "$(id -u)" -ne 0 ]; then
    error "This script must be run as root. Please use 'sudo' or run as the root user."
    exit 1
fi

# --- Static Configuration ---
GITHUB_USER="mersvpn"
GITHUB_REPO="mersyar-bot"

# --- Dynamic Configuration (Fetched from GitHub) ---
info "Fetching the latest release information from GitHub..."
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
TARBALL_NAME="${LATEST_TAG}.tar.gz"
DB_NAME="mersyar_bot_db"
DB_USER="mersyar"
# --- FIX: Generate URL-safe random strings for passwords and tokens ---
DB_PASSWORD=$(openssl rand -base64 18 | tr -dc 'a-zA-Z0-9' | head -c 16)
WEBHOOK_SECRET_TOKEN=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)


# 1. Update System and Install ALL Dependencies
info "[1/8] Updating system and installing all dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y wget tar $PYTHON_ALIAS-pip $PYTHON_ALIAS-venv nginx mysql-server python3-certbot-nginx \
phpmyadmin php-fpm php-mysql php-mbstring php-zip php-gd php-json php-curl

# 2. Download and Extract Latest Release
info "[2/8] Downloading release $LATEST_TAG from GitHub..."
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

# 3. Setting up MySQL Database and User
info "[3/8] Setting up MySQL Database and User..."
sudo mysql -e "CREATE DATABASE IF NOT EXISTS $DB_NAME;"
sudo mysql -e "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASSWORD';"
# --- FIX: Set authentication method to be compatible with phpMyAdmin ---
sudo mysql -e "ALTER USER '$DB_USER'@'localhost' IDENTIFIED WITH mysql_native_password BY '$DB_PASSWORD';"
sudo mysql -e "GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"
success "MySQL database and user created successfully."

# 4. Create .env file with ALL credentials
info "[4/8] Creating .env file..."
cat << EOF > .env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
AUTHORIZED_USER_IDS="${AUTHORIZED_USER_IDS}"
SUPPORT_USERNAME="${SUPPORT_USERNAME}"

# Webhook Configuration
BOT_DOMAIN="${DOMAIN}"
WEBHOOK_SECRET_TOKEN="${WEBHOOK_SECRET_TOKEN}"

# Database credentials
DB_HOST="localhost"
DB_NAME="${DB_NAME}"
DB_USER="${DB_USER}"
DB_PASSWORD="${DB_PASSWORD}"
EOF

# 5. Setup Python Virtual Environment
info "[5/8] Setting up Python virtual environment..."
$PYTHON_ALIAS -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 6. Setup phpMyAdmin
info "[6/8] Configuring phpMyAdmin..."
ln -s -f /usr/share/phpmyadmin /var/www/html/phpmyadmin
PHP_FPM_SOCK=$(ls /var/run/php/php*-fpm.sock | head -n 1)
if [ -z "$PHP_FPM_SOCK" ]; then
    error "Could not find PHP-FPM socket. Please install php-fpm manually."
    exit 1
fi
success "phpMyAdmin configured with PHP socket: $PHP_FPM_SOCK"

# 7. Configure Nginx (for Bot and phpMyAdmin) and Obtain SSL Certificate
info "[7/8] Configuring Nginx for Bot & phpMyAdmin, then obtaining SSL..."
cat << EOF > /etc/nginx/sites-available/$SERVICE_NAME
server {
    listen 80;
    server_name $DOMAIN;
    root /var/www/html;

    location /.well-known/acme-challenge/ { allow all; }

    location /phpmyadmin {
        index index.php index.html;
        location ~ \.php$ {
            include snippets/fastcgi-php.conf;
            fastcgi_pass unix:${PHP_FPM_SOCK};
        }
    }

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

# 8. Create and Enable systemd Service
info "[8/8] Creating and enabling the bot service..."
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
systemctl start $SERVICE_NAME

success "==============================================="
success "✅✅✅ Installation Complete! ✅✅✅"
success "The bot (version $LATEST_TAG) is now running on https://$DOMAIN"
success "phpMyAdmin is available at https://$DOMAIN/phpmyadmin"
info "To log into phpMyAdmin, use username '${DB_USER}' and the password stored in the .env file."
info "To check the bot service status, use: systemctl status $SERVICE_NAME"