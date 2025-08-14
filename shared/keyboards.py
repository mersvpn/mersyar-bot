from telegram import ReplyKeyboardMarkup, KeyboardButton
from config import config

def get_admin_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("👤 مدیریت کاربران")],
        [KeyboardButton("💰 تنظیمات مالی"), KeyboardButton("📨 ارسال پیام")],
        [KeyboardButton("⚙️ تنظیمات و ابزارها"), KeyboardButton("💻 ورود به پنل کاربری")],
        [KeyboardButton("ℹ️ راهنما")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_user_management_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("👥 نمایش کاربران"), KeyboardButton("⌛️ کاربران رو به اتمام")],
        [KeyboardButton("🔎 جستجوی کاربر"), KeyboardButton("➕ افزودن کاربر")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_settings_and_tools_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🔐 مدیریت پنل مرزبان")],
        [KeyboardButton("⏰ تنظیمات یادآور")],
        [KeyboardButton("⚙️ تنظیم کاربر الگو"), KeyboardButton("🔗 ایجاد لینک اتصال")],
        [KeyboardButton("🗒️ مدیریت یادداشت‌ها"), KeyboardButton("📝 پیگیری‌های فعال")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_customer_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard_layout = [
        [KeyboardButton("💳 خرید اشتراک")],
        [KeyboardButton("📊 سرویس من"), KeyboardButton("📱 دانلود و راهنمای اتصال")]
    ]
    if config.SUPPORT_USERNAME:
        keyboard_layout.append([KeyboardButton("💬 پشتیبانی")])
    return ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True)

def get_customer_view_for_admin_keyboard() -> ReplyKeyboardMarkup:
    keyboard_layout = [
        [KeyboardButton("📊 سرویس من")],
        [KeyboardButton("💳 خرید اشتراک"), KeyboardButton("📱 دانلود و راهنمای اتصال")],
        [KeyboardButton("↩️ بازگشت به پنل ادمین")]
    ]
    if config.SUPPORT_USERNAME:
        keyboard_layout[1].insert(1, KeyboardButton("💬 پشتیبانی"))
    return ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True)