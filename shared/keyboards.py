# FILE: shared/keyboards.py (COMPLETE AND CORRECT)

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import config

# =============================================================================
#  بخش کیبوردهای اصلی (ReplyKeyboardMarkup)
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
        [KeyboardButton("🛍️فــــــــــروشـــــــــــگاه")],
        [KeyboardButton("📊ســـــــــــرویس‌های من"), KeyboardButton("📱 راهــــــــــنمای اتصال")]
    ]
    if config.SUPPORT_USERNAME:
        keyboard_layout.append([KeyboardButton("💬 پشتیبانی")])
    return ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True)

def get_customer_shop_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("👨‍💻 ساخت اشتراک توسط پشتیبانی")],
        [KeyboardButton("♻️ اشتراک با حجم دلخواه"), KeyboardButton("💎 اشتراک با حجم نامحدود")],
        [KeyboardButton("🧾 ارسال رسید پرداخت")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_to_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_customer_view_for_admin_keyboard() -> ReplyKeyboardMarkup:
    keyboard_layout = [
        [KeyboardButton("🛍️فــــــــــروشـــــــــــگاه")],
        [KeyboardButton("📊ســـــــــــرویس‌های من"), KeyboardButton("📱 راهــــــــــنمای اتصال")]
    ]
    if config.SUPPORT_USERNAME:
        keyboard_layout.append([KeyboardButton("💬 پشتیبانی")])
    keyboard_layout.append([KeyboardButton("↩️ بازگشت به پنل ادمین")])
    return ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True)

def get_notes_management_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("🗒️ یادداشت‌های روزانه"), KeyboardButton("👤 اشتراک‌های ثبت‌شده")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_financial_settings_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton("💳 تنظیمات پرداخت"), KeyboardButton("📊 مدیریت پلن‌های فروش")],
        [KeyboardButton("🔙 بازگشت به تنظیمات")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# =============================================================================
#  بخش کیبوردهای شیشه‌ای (InlineKeyboardMarkup)
# =============================================================================

def get_payment_methods_keyboard() -> InlineKeyboardMarkup:
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

def get_plan_management_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("💎 مدیریت پلن‌های نامحدود", callback_data="admin_manage_unlimited"),
            InlineKeyboardButton("💡 مدیریت پلن‌های حجمی", callback_data="admin_manage_volumetric")
        ],
        [
            InlineKeyboardButton("✏️ تنظیم نام پلن‌ها", callback_data="admin_set_plan_names")
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به تنظیمات مالی", callback_data="back_to_financial_settings")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)