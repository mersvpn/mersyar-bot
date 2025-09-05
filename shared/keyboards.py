# FILE: shared/keyboards.py (نسخه نهایی با دکمه تنظیم نام و کیبورد داینامیک)

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import config
# --- NEW: Import db_manager to fetch dynamic button names ---
from database import db_manager

# =============================================================================
#  بخش کیبوردهای اصلی (ReplyKeyboardMarkup) - بدون تغییر
# =============================================================================

def get_admin_main_menu_keyboard() -> ReplyKeyboardMarkup:
    # ... (این بخش بدون تغییر باقی می‌ماند)
    keyboard = [
        [KeyboardButton("👤 مدیریت کاربران")],
        [KeyboardButton("📓 مدیریت یادداشت‌ها"), KeyboardButton("⚙️ تنظیمات و ابزارها")],
        [KeyboardButton("📨 ارسال پیام"), KeyboardButton("💻 ورود به پنل کاربری")],
        [KeyboardButton("📚 تنظیمات آموزش")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_user_management_keyboard() -> ReplyKeyboardMarkup:
    # ... (این بخش بدون تغییر باقی می‌ماند)
    keyboard = [
        [KeyboardButton("👥 نمایش کاربران"), KeyboardButton("⌛️ کاربران رو به اتمام")],
        [KeyboardButton("🔎 جستجوی کاربر"), KeyboardButton("➕ افزودن کاربر")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_settings_and_tools_keyboard() -> ReplyKeyboardMarkup:
    # ... (این بخش بدون تغییر باقی می‌ماند)
    keyboard = [
        [KeyboardButton("🔐 مدیریت پنل مرزبان")],
        [KeyboardButton("🔧 تنظیمات ربات"), KeyboardButton("💰 تنظیمات مالی")],
        [KeyboardButton("📣 تنظیم کانال گزارش")],
        [KeyboardButton("🛠️ ابزارهای کمکی"), KeyboardButton("📊 آمار ربات")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_helper_tools_keyboard() -> ReplyKeyboardMarkup:
    # ... (این بخش بدون تغییر باقی می‌ماند)
    keyboard = [
        [KeyboardButton("⚙️ اتوماسیون روزانه"), KeyboardButton("⚙️ تنظیم کاربر الگو")],
        [KeyboardButton("🔗 ایجاد لینک اتصال")],
        [KeyboardButton("🔙 بازگشت به تنظیمات")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_customer_main_menu_keyboard() -> ReplyKeyboardMarkup:
    # ... (این بخش بدون تغییر باقی می‌ماند)
    keyboard_layout = [
        [KeyboardButton("🛍️ پنل خرید و پرداخت")],
        [KeyboardButton("📊 سرویس من"), KeyboardButton("📱 دانلود و راهنمای اتصال")]
    ]
    if config.SUPPORT_USERNAME:
        keyboard_layout.append([KeyboardButton("💬 پشتیبانی")])
    return ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True)

def get_customer_view_for_admin_keyboard() -> ReplyKeyboardMarkup:
    # ... (این بخش بدون تغییر باقی می‌ماند)
    keyboard_layout = [
        [KeyboardButton("🛍️ پنل خرید و پرداخت")],
        [KeyboardButton("📊 سرویس من"), KeyboardButton("📱 دانلود و راهنمای اتصال")]
    ]
    if config.SUPPORT_USERNAME:
        keyboard_layout.append([KeyboardButton("💬 پشتیبانی")])
    keyboard_layout.append([KeyboardButton("↩️ بازگشت به پنل ادمین")])
    return ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True)

def get_notes_management_keyboard() -> ReplyKeyboardMarkup:
    # ... (این بخش بدون تغییر باقی می‌ماند)
    keyboard = [
        [KeyboardButton("🗒️ یادداشت‌های روزانه"), KeyboardButton("👤 اشتراک‌های ثبت‌شده")],
        [KeyboardButton("🔙 بازگشت به منوی اصلی")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_financial_settings_keyboard() -> ReplyKeyboardMarkup:
    # ... (این بخش بدون تغییر باقی می‌ماند)
    keyboard = [
        [KeyboardButton("💳 تنظیمات پرداخت"), KeyboardButton("📊 مدیریت پلن‌های فروش")],
        [KeyboardButton("🔙 بازگشت به تنظیمات")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# =============================================================================
#  بخش کیبوردهای شیشه‌ای (InlineKeyboardMarkup)
# =============================================================================

def get_customer_purchase_menu_keyboard() -> InlineKeyboardMarkup:
    # ... (این بخش بدون تغییر باقی می‌ماند)
    keyboard = [
        [InlineKeyboardButton("👨‍💻 ارسال درخواست خرید", callback_data="customer_manual_purchase")],
        [
            InlineKeyboardButton("💡 ساخت پلن دلخواه", callback_data="show_plan_type_menu"),
            InlineKeyboardButton("🧾 ارسال رسید پرداخت", callback_data="customer_send_receipt")
        ],
        [InlineKeyboardButton("✖️ بستن", callback_data="close_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- MODIFIED: This function is now async to fetch names from the DB ---

async def get_plan_type_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Builds the plan type selection keyboard with dynamic names from bot_settings
    in a single-column layout.
    """
    settings = await db_manager.load_bot_settings()
    
    # Fetch custom names, or use defaults if not set
    unlimited_btn_text = settings.get("unlimited_plan_button_text", "💎 پلن نامحدود")
    volumetric_btn_text = settings.get("volumetric_plan_button_text", "📊 پلن حجمی")

    keyboard = [
        # Each button is now in its own row
        [InlineKeyboardButton(volumetric_btn_text, callback_data="customer_custom_purchase")],
        [InlineKeyboardButton(unlimited_btn_text, callback_data="customer_unlimited_purchase")],
        [InlineKeyboardButton("🔙 بازگشت به پنل خرید", callback_data="back_to_purchase_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_payment_methods_keyboard() -> InlineKeyboardMarkup:
    # ... (این بخش بدون تغییر باقی می‌ماند)
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

# --- MODIFIED: Added a new button for managing button names ---
def get_plan_management_keyboard() -> InlineKeyboardMarkup:
    """
    کیبورد شیشه‌ای برای منوی "مدیریت پلن‌های فروش" با چیدمان دو ستونه.
    """
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