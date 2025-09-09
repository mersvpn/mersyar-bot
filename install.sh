#!/bin/bash
set -e

# --- Helper Functions for Colors ---
info() { echo -e "\e[34m[INFO]\e[0m $1"; }
success() { echo -e "\e[32m[SUCCESS]\e[0m $1"; }
error() { echo -e "\e[31m[ERROR]\e[0m $1"; }
warning() { echo -e "\e[33m[WARN]\e[0m $1"; }

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

# --- Script Internal Variables ---
PROJECT_DIR="/root/$GITHUB_REPO"
SERVICE_NAME="mersyar-bot"
PYTHON_ALIAS="python3"
TARBALL_NAME="${LATEST_TAG}.tar.gz"
DB_NAME="mersyar_bot_db"
DB_USER="mersyar"

# --- Interactive User Input ---
# This block runs only if the .env file does not exist, making updates seamless.
if [ ! -f "$PROJECT_DIR/.env" ]; then
    read -p "Enter your Domain/Subdomain (e.g., bot.example.com): " DOMAIN
    read -p "Enter your email for SSL certificate notifications: " ADMIN_EMAIL
    echo "---"
    read -p "Enter your Telegram Bot Token: " TELEGRAM_BOT_TOKEN
    read -p "Enter the numeric Telegram Admin User ID: " AUTHORIZED_USER_IDS
    read -p "Enter the Support Username (optional, press Enter to skip): " SUPPORT_USERNAME
else
    info "Existing .env file found. Skipping user input for credentials."
    # We still need the domain for nginx/certbot checks
    DOMAIN=$(grep -E "^BOT_DOMAIN=" "$PROJECT_DIR/.env" | cut -d '=' -f2- | tr -d '"')
    ADMIN_EMAIL="info@$DOMAIN" # Fallback email
fi

info "✅ Starting the installation/update process..."
sleep 2

# --- 1. Update System and Install ALL Dependencies ---
info "[1/9] Updating system and installing dependencies..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y wget tar $PYTHON_ALIAS-pip $PYTHON_ALIAS-venv nginx mysql-server python3-certbot-nginx \
phpmyadmin php-fpm php-mysql php-mbstring php-zip php-gd php-json php-curl

# --- 2. Download and Extract Latest Release ---
info "[2/9] Downloading release $LATEST_TAG..."
wget -q "$DOWNLOAD_URL" -O "/tmp/$TARBALL_NAME"

# --- 3. Smart Update/Install Logic ---
if [ -d "$PROJECT_DIR" ]; then
    info "[3/9] Existing installation found. Performing an update..."
else
    info "[3/9] No existing installation found. Performing a fresh install..."
    mkdir -p "$PROJECT_DIR"
fi

# Extract files into the project directory
tar -xzf "/tmp/$TARBALL_NAME" --strip-components=1 -C "$PROJECT_DIR"
rm -f "/tmp/$TARBALL_NAME"

# --- 🟢 IMPROVEMENT: Move all subsequent operations inside the project directory ---
cd "$PROJECT_DIR" || { error "Failed to enter project directory: $PROJECT_DIR"; exit 1; }

# --- 3.1. Setup Database and .env (ONLY for fresh install) ---
if [ ! -f ".env" ]; then
    info "   -> Setting up MySQL Database and User for the first time..."
    DB_PASSWORD=$(openssl rand -base64 18 | tr -dc 'a-zA-Z0-9' | head -c 16)
    sudo mysql -e "CREATE DATABASE IF NOT EXISTS $DB_NAME;"
    sudo mysql -e "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED WITH mysql_native_password BY '$DB_PASSWORD';"
    sudo mysql -e "GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';"
    sudo mysql -e "FLUSH PRIVILEGES;"
    
    info "   -> Creating .env file..."
    WEBHOOK_SECRET_TOKEN=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)
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
fi

# --- 4. Setup Python Virtual Environment ---
info "[4/9] Setting up Python virtual environment..."
$PYTHON_ALIAS -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# --- 5. Setup phpMyAdmin ---
info "[5/9] Configuring phpMyAdmin..."
# Ensure the symlink is correct, even after updates
ln -s -f /usr/share/phpmyadmin /var/www/html/phpmyadmin
PHP_FPM_SOCK=$(ls /var/run/php/php*-fpm.sock | head -n 1)

# --- 6. Configure Nginx and Obtain SSL Certificate ---
info "[6/9] Configuring Nginx and obtaining SSL..."
# Check if nginx config needs to be created
if [ ! -f "/etc/nginx/sites-available/$SERVICE_NAME" ]; then
    cat << EOF > /etc/nginx/sites-available/$SERVICE_NAME
server {
    listen 80; server_name $DOMAIN; root /var/www/html;
    location /.well-known/acme-challenge/ { allow all; }
    location /phpmyadmin { index index.php; location ~ \.php$ { include snippets/fastcgi-php.conf; fastcgi_pass unix:${PHP_FPM_SOCK}; } }
    # All other requests are proxied to the bot
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
else
    info "Nginx configuration already exists. Skipping creation."
    # Ensure certbot renewal is set up
    certbot renew --quiet
fi

# --- 7. Create and Enable systemd Service ---
info "[7/9] Creating/Updating the bot service..."
cat << EOF > /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=$SERVICE_NAME Telegram Bot Service
After=network.target mysql.service
[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/bot.py
Restart=on-failure
RestartSec=10
[Install]
WantedBy=multi-user.target
EOF

# --- 8. Install Mersyar CLI Tool ---
info "[8/9] Installing 'mersyar' command-line tool..."
# Now this command is guaranteed to run from inside the project directory
if [ -f "mersyar" ]; then
    chmod +x "mersyar"
    ln -sf "$PROJECT_DIR/mersyar" /usr/local/bin/mersyar
    success "'mersyar' tool installed successfully."
else
    warning "'mersyar' script not found in the downloaded files. Skipping installation of CLI tool."
fi

# --- 9. Finalizing ---
info "[9/9] Finalizing and starting services..."
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

success "==============================================="
success "✅✅✅ Update/Install Complete! ✅✅✅"
info "The bot (version $LATEST_TAG) is now running."
info "To manage the bot, you can now simply type: mersyar"
info "To check the bot service status, use: systemctl status $SERVICE_NAME"