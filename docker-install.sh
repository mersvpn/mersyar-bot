#!/bin/bash
set -e

# --- Helper Functions for Colors ---
info() { echo -e "\e[34m[INFO]\e[0m $1"; }
success() { echo -e "\e[32m[SUCCESS]\e[0m $1"; }
error() { echo -e "\e[31m[ERROR]\e[0m $1"; }
warning() { echo -e "\e[33m[WARN]\e[0m $1"; }

# --- Static Config ---
PROJECT_DIR="/root/mersyar-docker"
INSTALL_SCRIPT_PATH="/root/mersyar-install.sh" # Note: a copy is stored for re-runs
CLI_COMMAND_PATH="/usr/local/bin/mersyar"

# ==============================================================================
#                              MANAGEMENT MENU
# ==============================================================================
manage_bot() {
    # FIX: Ensure all commands run from the correct directory
    cd "$PROJECT_DIR"
    
    show_menu() {
       echo -e "\n--- Mersyar Bot Docker Manager ---"
       echo " 1) View Bot Logs (Live)"
       echo " 2) Restart Bot"
       echo " 3) Stop Bot & All Services"
       echo " 4) Start Bot & All Services"
       echo " 5) Update Bot (from GitHub Latest Release)"
       echo " 6) Re-run Installation / Change Settings"
       echo " 7) Exit"
       echo "------------------------------------"
       read -p "Select an option [1-7]: " option
       handle_option "$option"
    }

    handle_option() {
       # We are already in PROJECT_DIR from the start of manage_bot()
       case $1 in
           1)
               info "Tailing logs for mersyar-bot. Press Ctrl+C to exit."
               docker compose logs -f bot
               show_menu
               ;;
           2)
               info "Restarting mersyar-bot container..."
               if docker compose restart bot; then success "Bot restarted."; else error "Failed to restart bot."; fi
               show_menu
               ;;
           3)
               info "Stopping all services (bot, db, phpmyadmin)..."
               if docker compose down; then success "All services stopped."; else error "Failed to stop services."; fi
               show_menu
               ;;
           4)
               info "Starting all services..."
               if docker compose up -d; then success "All services started in the background."; else error "Failed to start services."; fi
               show_menu
               ;;
           5)
               info "Updating bot by rebuilding the image from GitHub..."
               warning "This may take a few minutes."
               # FIX: Add --build-arg to bust the Docker cache for downloads
               if docker compose up -d --build --build-arg CACHE_BUSTER=$(date +%s); then
                   success "Bot updated successfully!"
               else
                   error "Failed to update the bot."
               fi
               show_menu
               ;;
           6)
               warning "This will re-run the full installation process from the stored script."
               read -p "Are you sure you want to continue? (y/n): " confirm
               if [[ "$confirm" == "y" ]]; then
                   # Run the original installer script again
                   bash "$INSTALL_SCRIPT_PATH"
               else
                   info "Operation cancelled."
                   show_menu
               fi
               ;;
           7)
               echo "Exiting."
               exit 0
               ;;
           *)
               error "Invalid option. Please try again."
               show_menu
               ;;
       esac
    }
    
    show_menu
}

# ==============================================================================
#                              INSTALLATION LOGIC
# ==============================================================================
install_bot() {
    info "==============================================="
    info "      Mersyar-Bot Docker Installer"
    info "==============================================="

    # --- 1. Install Docker ---
    # ... (Installation logic remains the same)
    info "[1/7] Checking for Docker..."
    if ! command -v docker &> /dev/null; then
        warning "Docker not found. Installing Docker..."
        curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh && rm get-docker.sh
        success "Docker installed successfully."
    else
        success "Docker is already installed."
    fi
    if ! docker compose version &> /dev/null; then
        warning "Docker Compose plugin not found. Installing..."
        apt-get update -y > /dev/null && apt-get install -y docker-compose-plugin > /dev/null
        success "Docker Compose plugin installed successfully."
    else
        success "Docker Compose plugin is already installed."
    fi

    # --- 2. User Input ---
    # ... (User input logic remains the same)
    info "[2/7] Gathering required information..."
    read -p "Enter your Domain/Subdomain (e.g., bot.yourdomain.com): " BOT_DOMAIN
    read -p "Enter your email for SSL notifications: " ADMIN_EMAIL
    echo "---"
    read -p "Enter Telegram Bot Token: " TELEGRAM_BOT_TOKEN
    read -p "Enter Telegram Admin User ID: " AUTHORIZED_USER_IDS
    read -p "Enter Support Username (optional): " SUPPORT_USERNAME

    # --- 3. Create Project Directory and Files ---
    info "[3/7] Creating project structure at $PROJECT_DIR..."
    mkdir -p "$PROJECT_DIR"
    cd "$PROJECT_DIR"

    info "-> Generating secure random strings for secrets..."
    WEBHOOK_SECRET_TOKEN=$(openssl rand -hex 32)
    DB_ROOT_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 20)
    DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 20)

    info "-> Creating .env file..."
    cat << EOF > .env
# --- Telegram Bot Settings ---
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}"
AUTHORIZED_USER_IDS="${AUTHORIZED_USER_IDS}"
SUPPORT_USERNAME="${SUPPORT_USERNAME}"
# --- Webhook Settings ---
BOT_DOMAIN="${BOT_DOMAIN}"
WEBHOOK_SECRET_TOKEN="${WEBHOOK_SECRET_TOKEN}"
BOT_PORT=8081
# --- Database Settings for Docker Compose ---
DB_ROOT_PASSWORD="${DB_ROOT_PASSWORD}"
DB_NAME="mersyar_bot_db"
DB_USER="mersyar"
DB_PASSWORD="${DB_PASSWORD}"
# --- Database Connection Settings for the Bot ---
DB_HOST="db"
# --- Admin Email for Certbot ---
ADMIN_EMAIL="${ADMIN_EMAIL}"
EOF

    info "-> Creating Dockerfile with cache-busting..."
    # FIX: Dockerfile now includes the cache-busting argument
    cat << 'EOF' > Dockerfile
FROM python:3.10-slim-bookworm
RUN apt-get update && apt-get install -y wget tar && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ARG GITHUB_USER="mersvpn"
ARG GITHUB_REPO="mersyar-bot"
ARG CACHE_BUSTER=1
WORKDIR /app
RUN echo "Busting cache with value: ${CACHE_BUSTER}" && \
    LATEST_TAG=$(wget -qO- "https://api.github.com/repos/${GITHUB_USER}/${GITHUB_REPO}/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/') && \
    DOWNLOAD_URL="https://github.com/${GITHUB_USER}/${GITHUB_REPO}/archive/refs/tags/${LATEST_TAG}.tar.gz" && \
    wget -q "$DOWNLOAD_URL" -O latest_release.tar.gz && \
    tar -xzf latest_release.tar.gz --strip-components=1 && \
    rm latest_release.tar.gz
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "bot.py"]
EOF

    info "-> Creating docker-compose.yml with healthchecks..."
    # (The docker-compose.yml content is already correct, no changes needed here)
    cat << 'EOF' > docker-compose.yml
version: '3.8'
services:
  bot:
    build: .
    container_name: mersyar-bot
    restart: unless-stopped
    ports:
      - "127.0.0.1:8081:8081"
    env_file:
      - .env
    networks:
      - mersyar-net
    depends_on:
      db:
        condition: service_healthy

  db:
    image: mysql:8.0
    container_name: mersyar-db
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
      MYSQL_DATABASE: ${DB_NAME}
      MYSQL_USER: ${DB_USER}
      MYSQL_PASSWORD: ${DB_PASSWORD}
    volumes:
      - mysql_data:/var/lib/mysql
    networks:
      - mersyar-net
    healthcheck:
      test: ["CMD", "mysqladmin" ,"ping", "-h", "localhost", "-u", "root", "-p${DB_ROOT_PASSWORD}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  phpmyadmin:
    image: phpmyadmin/phpmyadmin
    container_name: mersyar-pma
    restart: unless-stopped
    environment:
      PMA_HOST: db
      PMA_PORT: 3306
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
    ports:
      - "127.0.0.1:8082:80"
    networks:
      - mersyar-net
    depends_on:
      db:
        condition: service_healthy

networks:
  mersyar-net:
    driver: bridge

volumes:
  mysql_data:
EOF

    # --- 4. Build and Run Docker Containers ---
    info "[4/7] Building and starting Docker containers... (This may take a few minutes)"
    docker compose up --build -d

    # --- 5. Configure Nginx ---
    # ... (Nginx logic remains the same)
    info "[5/7] Configuring Nginx reverse proxy..."
    if ! command -v nginx &> /dev/null; then warning "Nginx not found. Installing..." && apt-get update -y > /dev/null && apt-get install -y nginx > /dev/null; fi
    mkdir -p /etc/nginx/sites-available/ /etc/nginx/sites-enabled/
    NGINX_CONF="/etc/nginx/sites-available/mersyar-bot"
    cat << EOF > "$NGINX_CONF"
server {
    listen 80;
    server_name ${BOT_DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/

    # --- 6. Obtain SSL Certificate ---
    # ... (Certbot logic remains the same)
    info "[6/7] Obtaining SSL certificate with Certbot..."
    info "-> Ensuring Certbot and Nginx plugin are installed..."
    apt-get update -y > /dev/null && apt-get install -y certbot python3-certbot-nginx > /dev/null
    nginx -t && systemctl restart nginx
    certbot --nginx -d "${BOT_DOMAIN}" --non-interactive --agree-tos --email "${ADMIN_EMAIL}" --redirect

    # --- 7. Finalizing ---
    info "[7/7] Finalizing the installation..."
    # Create the management command
    # Store a copy of the installer script used
    cp "$0" "$INSTALL_SCRIPT_PATH"
    chmod +x "$INSTALL_SCRIPT_PATH"
    # Create/update the CLI command that points to the main management function
    cat << 'EOF' > "$CLI_COMMAND_PATH"
#!/bin/bash
# This is a wrapper to call the main script's management function.
# It ensures that even if the installer script is updated, the 'mersyar' command still works.
source "$INSTALL_SCRIPT_PATH"
manage_bot "$@"
EOF
    chmod +x "$CLI_COMMAND_PATH"
    success "CLI command 'mersyar' created/updated."
    
    systemctl restart nginx

    # --- ✅ Installation Summary ---
    # ... (Summary remains the same)
    success "==============================================="
    success "✅✅✅ Mersyar-Bot Docker Installation Complete! ✅✅✅"
    info "You can now manage your bot by running the 'mersyar' command."
    echo ""
    echo -e "\e[36m🌐 Bot Domain:\e[0m https://${BOT_DOMAIN}"
    echo -e "\e[36m🔑 phpMyAdmin:\e[0m http://127.0.0.1:8082 (Access via SSH tunnel: ssh -L 8082:127.0.0.1:8082 root@<SERVER_IP>)"
    echo -e "\e[36m🔒 Database Password:\e[0m ${DB_PASSWORD}"
    success "==============================================="
}

# ==============================================================================
#                                 MAIN LOGIC
# ==============================================================================
# If the script is run with the name 'mersyar' or if the project exists, show the menu.
# Otherwise, start the installation.
if [[ "$(basename "$0")" == "mersyar" || -f "$PROJECT_DIR/docker-compose.yml" ]]; then
    manage_bot "$@"
else
    # This is a fresh install. We save the path to this script so we can re-run it later.
    INSTALL_SCRIPT_PATH_SRC="${BASH_SOURCE[0]}"
    install_bot
fi