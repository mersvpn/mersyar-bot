# FILE: shared/keyboards.py (نسخه نهایی شده)

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import config

# =============================================================================
#  بخش کیبوردهای اصلی (بدون تغییر)
# =============================================================================

def get_admin_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("👤 مدیریت کاربران")],
        [KeyboardButton("📓 مدیریت یادداشت‌ها"), KeyboardButton("⚙️ تنظیمات و ابزارها")],
        [KeyboardButton("📨 ارسال پیام"), KeyboardButton("💻 ورود به پنل کاربری")],
        [KeyboardButton("📚 تنظیمات آموزش")]
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

def get_helper_tools_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("⚙️ اتوماسیون روزانه"), KeyboardButton("⚙️ تنظیم کاربر الگو")],
        [KeyboardButton("🔗 ایجاد لینک اتصال")],
        [KeyboardButton("🔙 بازگشت به تنظیمات")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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


# =============================================================================
#  بخش جدید: کیبوردهای مربوط به پنل خرید دلخواه و تنظیمات مالی جدید
# =============================================================================

# FILE: shared/keyboards.py (فقط این تابع را جایگزین کنید)

def get_customer_purchase_menu_keyboard() -> InlineKeyboardMarkup:
    """
    کیبورد شیشه‌ای جدید برای منوی "پنل خرید و پرداخت" مشتری.
    """
    keyboard = [
        [InlineKeyboardButton("👨‍💻 ارسال درخواست خرید", callback_data="customer_manual_purchase")],
        [
            # --- FIX: Changed callback_data to match the ConversationHandler's entry_point ---
            InlineKeyboardButton("💡 ساخت پلن دلخواه", callback_data="customer_custom_purchase"),
            InlineKeyboardButton("🧾 ارسال رسید پرداخت", callback_data="customer_send_receipt")
        ],
        [InlineKeyboardButton("✖️ بستن", callback_data="close_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)
def get_financial_settings_keyboard() -> ReplyKeyboardMarkup:
    """
    کیبورد معمولی جدید برای منوی "تنظیمات مالی" ادمین.
    """
    keyboard = [
        [KeyboardButton("💳 تنظیمات پرداخت"), KeyboardButton("💰 تنظیم قیمت‌گذاری دلخواه")],
        [KeyboardButton("🔙 بازگشت به تنظیمات")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_payment_methods_keyboard() -> InlineKeyboardMarkup:
    """
    کیبورد شیشه‌ای برای زیرمنوی "تنظیمات پرداخت" ادمین.
    """
    keyboard = [
        [
            InlineKeyboardButton("💳 تنظیم کارت به کارت", callback_data="admin_set_card_info"),
            InlineKeyboardButton("🅿️ تنظیم درگاه پرداخت (بزودی)", callback_data="coming_soon")
        ],
        [
            InlineKeyboardButton("₿ تنظیم پرداخت با رمز ارز (بزودی)", callback_data="coming_soon")
        ],
        [InlineKeyboardButton("🔙 بازگشت به تنظیمات مالی", callback_data="back_to_financial_settings")]
    ]
    return InlineKeyboardMarkup(keyboard)