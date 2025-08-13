# ===== IMPORTS & DEPENDENCIES =====
from telegram import ReplyKeyboardMarkup, KeyboardButton
from config import config # Needed for dynamically showing the support button

# ===== ADMIN PANEL KEYBOARDS =====

def get_admin_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Returns the main ReplyKeyboardMarkup for administrators.
    Layout: User-Focused (Style 1)
    """
    keyboard = [
        [KeyboardButton("👤 مدیریت کاربران")],
        [KeyboardButton("💰 تنظیمات مالی"), KeyboardButton("📨 ارسال پیام")],
        [KeyboardButton("⚙️ تنظیمات و ابزارها"), KeyboardButton("💻 ورود به پنل کاربری")],
        [KeyboardButton("ℹ️ راهنما")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_user_management_keyboard() -> ReplyKeyboardMarkup:
    """Returns the ReplyKeyboardMarkup for the 'User Management' section."""
    keyboard = [
        [KeyboardButton("👥 نمایش کاربران"), KeyboardButton("⌛️ کاربران رو به اتمام")],
        [KeyboardButton("🔎 جستجوی کاربر"), KeyboardButton("➕ افزودن کاربر")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# shared/keyboards.py

def get_settings_and_tools_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🔐 مدیریت پنل مرزبان")], # <-- دکمه جدید
        [KeyboardButton("⏰ تنظیمات یادآور")],
        [KeyboardButton("⚙️ تنظیم کاربر الگو"), KeyboardButton("🔗 ایجاد لینک اتصال")],
        [KeyboardButton("🗒️ یادداشت روز"), KeyboardButton("📝 پیگیری‌های فعال")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
# ===== CUSTOMER PANEL KEYBOARDS =====

def get_customer_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Returns the main ReplyKeyboardMarkup for regular customers.
    Layout: Prominent 'Purchase' button, custom layout.
    """
    keyboard_layout = [
        # Row 1: The main call to action
        [KeyboardButton("💳 خرید اشتراک")],
        
        # Row 2: Secondary actions
        [KeyboardButton("📊 سرویس من"), KeyboardButton("📱 دانلود و راهنمای اتصال")]
    ]

    # Row 3 (Optional): Support button, appears only if configured
    if config.SUPPORT_USERNAME:
        keyboard_layout.append([KeyboardButton("💬 پشتیبانی")])

    return ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True)

def get_customer_view_for_admin_keyboard() -> ReplyKeyboardMarkup:
    """
    Returns the customer menu but with a 'Back to Admin Panel' button.
    This is for when an admin is simulating the customer view.
    """
    keyboard_layout = [
        [KeyboardButton("📊 سرویس من")],
        [KeyboardButton("💳 خرید اشتراک"), KeyboardButton("📱 دانلود و راهنمای اتصال")],
        [KeyboardButton("↩️ بازگشت به پنل ادمین")]
    ]
    if config.SUPPORT_USERNAME:
        keyboard_layout[1].insert(1, KeyboardButton("💬 پشتیبانی"))
    return ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True)