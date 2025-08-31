# FILE: shared/keyboards.py (نسخه اصلاح شده)

from telegram import ReplyKeyboardMarkup, KeyboardButton
from config import config

def get_admin_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("👤 مدیریت کاربران")],
        [KeyboardButton("📓 مدیریت یادداشت‌ها"), KeyboardButton("⚙️ تنظیمات و ابزارها")],
        [KeyboardButton("📨 ارسال پیام"), KeyboardButton("💻 ورود به پنل کاربری")],
        # ======================== START: MODIFICATION ========================
        [KeyboardButton("📚 تنظیمات آموزش")] # Changed from "ℹ️ راهنما"
        # ========================= END: MODIFICATION =========================
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
        [KeyboardButton("🔧 تنظیمات ربات"), KeyboardButton("💰 تنظیمات مالی")],
        [KeyboardButton("📣 تنظیم کانال گزارش")],
        [KeyboardButton("🛠️ ابزارهای کمکی"), KeyboardButton("📊 آمار ربات")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== تابع اصلاح شده ====================
def get_helper_tools_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("⚙️ اتوماسیون روزانه"), KeyboardButton("⚙️ تنظیم کاربر الگو")],
        [KeyboardButton("🔗 ایجاد لینک اتصال")],
        [KeyboardButton("🔙 بازگشت به تنظیمات")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
# =======================================================

def get_customer_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard_layout = [
        [KeyboardButton("🛍️ پنل خرید و پرداخت")],
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

def get_notes_management_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🗒️ یادداشت‌های روزانه"), KeyboardButton("👤 اشتراک‌های ثبت‌شده")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)