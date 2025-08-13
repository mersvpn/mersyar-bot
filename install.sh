#!/bin/bash
set -e # در صورت بروز خطا، اسکریپت متوقف می‌شود

# ==================== پیکربندی ثابت ====================
# آدرس مخزن گیت‌هاب شما
REPO_URL="https://github.com/mersvpn/mersyar-bot.git"
# دامنه شما که به IP سرور متصل شده است
DOMAIN="mersyar.dorsa.of.to"
# آدرس ایمیل شما برای اطلاع‌رسانی‌های انقضای گواهی SSL
ADMIN_EMAIL="kdamin07@gmail.com"

# ==================== شروع اسکریپت ====================

echo "==============================================="
echo "  نصب تعاملی ربات مرزیار (Mersyar-Bot)  "
echo "==============================================="
echo "لطفاً اطلاعات زیر را با دقت وارد کنید."
echo ""

# --- پرسیدن اطلاعات به صورت تعاملی ---
read -p "1. توکن ربات تلگرام (TELEGRAM_BOT_TOKEN) را وارد کنید: " TELEGRAM_BOT_TOKEN
read -p "2. آیدی عددی ادمین تلگرام را وارد کنید: " AUTHORIZED_USER_IDS
read -p "3. یوزرنیم پشتیبانی را وارد کنید (اختیاری، برای رد کردن اینتر بزنید): " SUPPORT_USERNAME

echo ""
echo "✅ اطلاعات با موفقیت دریافت شد. شروع فرآیند نصب..."
sleep 2

# متغیرهای داخلی اسکریپت
PROJECT_DIR="/root/mersyar-bot"
SERVICE_NAME="mersyar-bot"
PYTHON_ALIAS="python3"
WEBHOOK_SECRET_TOKEN=$(head /dev/urandom | tr -dc A-Za-z0-9 | head -c 32)

# 1. آپدیت سیستم و نصب نیازمندی‌های پایه
echo ">>> [1/6] آپدیت و نصب نیازمندی‌ها..."
apt-get update
apt-get install -y git $PYTHON_ALIAS-pip $PYTHON_ALIAS-venv nginx python3-certbot-nginx

# 2. کلون کردن پروژه از گیت‌هاب
echo ">>> [2/6] دریافت پروژه از گیت‌هاب..."
if [ -d "$PROJECT_DIR" ]; then
    echo "پوشه پروژه وجود دارد. در حال دریافت آخرین تغییرات..."
    git -C $PROJECT_DIR pull
else
    git clone $REPO_URL $PROJECT_DIR
fi
cd $PROJECT_DIR

# 3. ساخت فایل .env با اطلاعات دریافت شده
echo ">>> [3/6] ساخت فایل .env..."
cat << EOF > .env
TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN"
AUTHORIZED_USER_IDS="$AUTHORIZED_USER_IDS"
SUPPORT_USERNAME="$SUPPORT_USERNAME"
WEBHOOK_SECRET_TOKEN="$WEBHOOK_SECRET_TOKEN"
BOT_DOMAIN="$DOMAIN"
EOF

# 4. راه‌اندازی محیط مجازی پایتون و نصب کتابخانه‌ها
echo ">>> [4/6] راه‌اندازی محیط پایتون..."
$PYTHON_ALIAS -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 5. تنظیم وب‌سرور Nginx و دریافت گواهی SSL
echo ">>> [5/6] پیکربندی Nginx و SSL..."
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
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email $ADMIN_EMAIL --redirect

# 6. ساخت و فعال‌سازی سرویس systemd
echo ">>> [6/6] ساخت سرویس دائمی برای ربات..."
cat << EOF > /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=Mersyar Telegram Bot Service
After=network.target
[Service]
User=root
Group=root
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/bot.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo "✅✅✅ نصب با موفقیت انجام شد! ✅✅✅"
echo "مهم: برای فعال‌سازی کامل، به ربات بروید و از منوی 'تنظیمات و ابزارها'، اطلاعات پنل مرزبان را وارد کنید."