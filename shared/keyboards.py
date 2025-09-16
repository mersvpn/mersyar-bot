# FILE: shared/keyboards.py (REVISED FOR I18N)

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import config
# Import the translator
from shared.translator import _

# =============================================================================
#  ReplyKeyboardMarkup Section
# =============================================================================

def get_admin_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(_("keyboards.admin_main_menu.user_management"))],
        [KeyboardButton(_("keyboards.admin_main_menu.notes_management")), KeyboardButton(_("keyboards.admin_main_menu.settings_and_tools"))],
        [KeyboardButton(_("keyboards.admin_main_menu.send_message")), KeyboardButton(_("keyboards.admin_main_menu.customer_panel_view"))],
        [KeyboardButton(_("keyboards.admin_main_menu.guides_settings"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_user_management_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(_("keyboards.user_management.show_users")), KeyboardButton(_("keyboards.user_management.expiring_users"))],
        [KeyboardButton(_("keyboards.user_management.search_user")), KeyboardButton(_("keyboards.user_management.add_user"))],
        [KeyboardButton(_("keyboards.user_management.back_to_main_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_settings_and_tools_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(_("keyboards.settings_and_tools.marzban_panel_management"))],
        [KeyboardButton(_("keyboards.settings_and_tools.bot_settings")), KeyboardButton(_("keyboards.settings_and_tools.financial_settings"))],
        [KeyboardButton(_("keyboards.settings_and_tools.set_log_channel"))],
        [KeyboardButton(_("keyboards.settings_and_tools.helper_tools")), KeyboardButton(_("keyboards.settings_and_tools.bot_stats"))],
        [KeyboardButton(_("keyboards.settings_and_tools.back_to_main_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_helper_tools_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(_("keyboards.helper_tools.daily_automation")), KeyboardButton(_("keyboards.helper_tools.set_template_user"))],
        [KeyboardButton(_("keyboards.helper_tools.create_connect_link"))],
        [KeyboardButton(_("keyboards.helper_tools.back_to_settings"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_customer_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard_layout = [
        [KeyboardButton(_("keyboards.customer_main_menu.shop"))],
        [KeyboardButton(_("keyboards.customer_main_menu.my_services")), KeyboardButton(_("keyboards.customer_main_menu.connection_guide"))]
    ]
    if config.SUPPORT_USERNAME:
        keyboard_layout.append([KeyboardButton(_("keyboards.customer_main_menu.support"))])
    return ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True)

def get_customer_shop_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(_("keyboards.customer_shop.assisted_purchase"))],
        [KeyboardButton(_("keyboards.customer_shop.custom_volume_plan")), KeyboardButton(_("keyboards.customer_shop.unlimited_volume_plan"))],
        [KeyboardButton(_("keyboards.customer_shop.send_receipt"))],
        [KeyboardButton(_("keyboards.customer_shop.back_to_main_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_to_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(_("keyboards.general.back_to_main_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_customer_view_for_admin_keyboard() -> ReplyKeyboardMarkup:
    keyboard_layout = [
        [KeyboardButton(_("keyboards.customer_main_menu.shop"))],
        [KeyboardButton(_("keyboards.customer_main_menu.my_services")), KeyboardButton(_("keyboards.customer_main_menu.connection_guide"))]
    ]
    if config.SUPPORT_USERNAME:
        keyboard_layout.append([KeyboardButton(_("keyboards.customer_main_menu.support"))])
    keyboard_layout.append([KeyboardButton(_("keyboards.general.back_to_admin_panel"))])
    return ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True)

def get_notes_management_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(_("keyboards.notes_management.daily_notes")), KeyboardButton(_("keyboards.notes_management.registered_subscriptions"))],
        [KeyboardButton(_("keyboards.notes_management.back_to_main_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_financial_settings_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(_("keyboards.financial_settings.payment_settings")), KeyboardButton(_("keyboards.financial_settings.sales_plan_management"))],
        [KeyboardButton(_("keyboards.financial_settings.back_to_settings"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# =============================================================================
#  InlineKeyboardMarkup Section (Unchanged, but good to keep for context)
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