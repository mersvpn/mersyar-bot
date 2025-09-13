#!/bin/bash
set -e

# --- Helper Functions for Colors ---
# ... (توابع رنگی بدون تغییر باقی می‌مانند) ...
info() { echo -e "\e[34m[INFO]\e[0m $1"; }
success() { echo -e "\e[32m[SUCCESS]\e[0m $1"; }
error() { echo -e "\e[31m[ERROR]\e[0m $1"; }
warning() { echo -e "\e[33m[WARN]\e[0m $1"; }

# --- Static Config ---
PROJECT_DIR="/root/mersyar-docker"
# FIX: Use the script's own path for re-runs
INSTALL_SCRIPT_PATH="$CLI_COMMAND_PATH" # The command itself is the persistent script
CLI_COMMAND_PATH="/usr/local/bin/mersyar"

# ==============================================================================
#                              MANAGEMENT MENU
# ==============================================================================
manage_bot() {
    cd "$PROJECT_DIR"
    
    show_menu() {
       # ... (منو بدون تغییر) ...
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
       cd "$PROJECT_DIR"
       case $1 in
           # ... (گزینه های 1 تا 4 بدون تغییر) ...
           1) info "Tailing logs..." && docker compose logs -f bot && show_menu ;;
           2) info "Restarting..." && (docker compose restart bot && success "Bot restarted." || error "Failed.") && show_menu ;;
           3) info "Stopping..." && (docker compose down && success "Stopped." || error "Failed.") && show_menu ;;
           4) info "Starting..." && (docker compose up -d && success "Started." || error "Failed.") && show_menu ;;
           5)
               info "Updating bot by rebuilding the image from GitHub..."
               warning "This may take a few minutes."
               # --- FIX: Use a two-step build/up process for compatibility ---
               info "Step 1: Building the new image..."
               if docker compose build --no-cache --build-arg CACHE_BUSTER=$(date +%s) bot; then
                   info "Step 2: Re-creating the container with the new image..."
                   if docker compose up -d; then
                       success "Bot updated successfully!"
                   else
                       error "Failed to re-create the container."
                   fi
               else
                   error "Failed to build the new image."
               fi
               show_menu
               ;;
           6)
               warning "This will re-run the full installation process."
               read -p "Are you sure you want to continue? (y/n): " confirm
               if [[ "$confirm" == "y" ]]; then
                   # The command itself is the script, so we run it with a special flag
                   bash "$CLI_COMMAND_PATH" --force-install
               else
                   info "Operation cancelled."
                   show_menu
               fi
               ;;
           7) echo "Exiting." && exit 0 ;;
           *) error "Invalid option." && show_menu ;;
       esac
    }
    
    show_menu
}

# ==============================================================================
#                              INSTALLATION LOGIC
# ==============================================================================
install_bot() {
    # ... (کل منطق نصب که قبلاً داشتید اینجا قرار می‌گیرد) ...
    # ... (شامل ایجاد Dockerfile اصلاح شده و docker-compose.yml) ...

    # FIX in Finalizing section:
    # --- 7. Finalizing ---
    info "[7/7] Finalizing the installation..."
    # The script copies itself to become the persistent command.
    cp "$0" "$CLI_COMMAND_PATH"
    chmod +x "$CLI_COMMAND_PATH"
    success "CLI command 'mersyar' created/updated."
    
    # ... (بقیه منطق نصب)
}

# ==============================================================================
#                                 MAIN LOGIC
# ==============================================================================
# Allow forcing re-installation
if [[ "$1" == "--force-install" ]]; then
    install_bot
    exit 0
fi

# Standard check to show menu or start install
if [[ -f "$CLI_COMMAND_PATH" && -f "$PROJECT_DIR/docker-compose.yml" ]]; then
    # Pass all arguments to manage_bot (e.g., for future command line flags)
    manage_bot "$@"
else
    install_bot
fi