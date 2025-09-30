# FILE: shared/keyboards.py (FINAL VERSION - NAMESPACE CORRECTED)

from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import config
from shared.translator import _
from database.db_manager import load_bot_settings

# =============================================================================
#  ReplyKeyboardMarkup Section
# =============================================================================

def get_admin_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        # --- FIX: All keys now use the 'keyboards.' namespace ---
        [KeyboardButton(_("keyboards.admin_main_menu.user_management"))],
        [KeyboardButton(_("keyboards.admin_main_menu.notes_management")), KeyboardButton(_("keyboards.admin_main_menu.settings_and_tools"))],
        [KeyboardButton(_("keyboards.admin_main_menu.send_message")), KeyboardButton(_("keyboards.admin_main_menu.customer_panel_view"))],
        [KeyboardButton(_("keyboards.admin_main_menu.guides_settings"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_user_management_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        # --- FIX: All keys now use the 'keyboards.' namespace ---
        [KeyboardButton(_("keyboards.user_management.show_users")), KeyboardButton(_("keyboards.user_management.expiring_users"))],
        [KeyboardButton(_("keyboards.user_management.search_user")), KeyboardButton(_("keyboards.user_management.add_user"))],
        [KeyboardButton(_("keyboards.user_management.back_to_main_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_settings_and_tools_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        # --- FIX: All keys now use the 'keyboards.' namespace ---
        [KeyboardButton(_("keyboards.settings_and_tools.marzban_panel_management"))],
        [KeyboardButton(_("keyboards.settings_and_tools.bot_settings")), KeyboardButton(_("keyboards.settings_and_tools.financial_settings"))],
        [KeyboardButton(_("keyboards.settings_and_tools.set_log_channel"))],
        [KeyboardButton(_("keyboards.settings_and_tools.helper_tools")), KeyboardButton(_("keyboards.settings_and_tools.bot_stats"))],
        [KeyboardButton(_("keyboards.settings_and_tools.back_to_main_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_helper_tools_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        # --- FIX: All keys now use the 'keyboards.' namespace ---
        [KeyboardButton(_("keyboards.helper_tools.daily_automation")), KeyboardButton(_("keyboards.helper_tools.set_template_user"))],
        [KeyboardButton(_("keyboards.helper_tools.create_connect_link")), KeyboardButton(_("keyboards.helper_tools.test_account_settings"))],
        [KeyboardButton(_("keyboards.helper_tools.back_to_settings"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def get_customer_main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    bot_settings = await load_bot_settings()
    is_wallet_enabled = bot_settings.get('is_wallet_enabled', False)
    
    # --- FIX: All keys now use the 'keyboards.' namespace ---
    keyboard_layout = [
        [KeyboardButton(_("keyboards.customer_main_menu.shop"))]
    ]
    second_row = [
        KeyboardButton(_("keyboards.customer_main_menu.my_services")),
        KeyboardButton(_("keyboards.customer_main_menu.test_account"))
    ]
    keyboard_layout.append(second_row)
    if is_wallet_enabled:
        keyboard_layout.append([KeyboardButton(_("keyboards.customer_main_menu.wallet_charge"))])
    last_row = [KeyboardButton(_("keyboards.customer_main_menu.connection_guide"))]
    if config.SUPPORT_USERNAME:
        last_row.append(KeyboardButton(_("keyboards.customer_main_menu.support")))
    keyboard_layout.append(last_row)
    
    return ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True)

def get_customer_shop_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        # --- FIX: All keys now use the 'keyboards.' namespace ---
        [KeyboardButton(_("keyboards.customer_shop.assisted_purchase"))],
        [KeyboardButton(_("keyboards.customer_shop.custom_volume_plan")), KeyboardButton(_("keyboards.customer_shop.unlimited_volume_plan"))],
        [KeyboardButton(_("keyboards.customer_shop.send_receipt"))],
        [KeyboardButton(_("keyboards.customer_shop.back_to_main_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_to_main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        # --- FIX: All keys now use the 'keyboards.' namespace ---
        [KeyboardButton(_("keyboards.general.back_to_main_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def get_customer_view_for_admin_keyboard() -> ReplyKeyboardMarkup:
    bot_settings = await load_bot_settings() 
    is_wallet_enabled = bot_settings.get('is_wallet_enabled', False)

    # --- FIX: All keys now use the 'keyboards.' namespace ---
    keyboard_layout = [
        [KeyboardButton(_("keyboards.customer_main_menu.shop"))]
    ]
    second_row = [
        KeyboardButton(_("keyboards.customer_main_menu.my_services")),
        KeyboardButton(_("keyboards.customer_main_menu.test_account"))
    ]
    keyboard_layout.append(second_row)
    if is_wallet_enabled: 
        keyboard_layout.append([KeyboardButton(_("keyboards.customer_main_menu.wallet_charge"))])
    last_row = [KeyboardButton(_("keyboards.customer_main_menu.connection_guide"))]
    if config.SUPPORT_USERNAME:
        last_row.append(KeyboardButton(_("keyboards.customer_main_menu.support")))
    keyboard_layout.append(last_row)
    # --- FIX: Added 'keyboards.' namespace ---
    keyboard_layout.append([KeyboardButton(_("keyboards.general.back_to_admin_panel"))])
    
    return ReplyKeyboardMarkup(keyboard_layout, resize_keyboard=True)

def get_notes_management_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        # --- FIX: All keys now use the 'keyboards.' namespace ---
        [KeyboardButton(_("keyboards.notes_management.daily_notes")), KeyboardButton(_("keyboards.notes_management.registered_subscriptions"))],
        [KeyboardButton(_("keyboards.notes_management.back_to_main_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_financial_settings_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        # --- FIX: All keys now use the 'keyboards.' namespace ---
        [KeyboardButton(_("keyboards.financial_settings.payment_settings")), KeyboardButton(_("keyboards.financial_settings.sales_plan_management"))],
        [KeyboardButton(_("keyboards.financial_settings.back_to_settings"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(_("keyboards.helper_tools.back_to_settings"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# =============================================================================
#  InlineKeyboardMarkup Section
# =============================================================================

def get_payment_methods_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        # --- FIX: All keys now use the 'keyboards.' namespace ---
        [
            InlineKeyboardButton(_("keyboards.inline_keyboards.payment_methods.set_card_info"), callback_data="admin_set_card_info"),
            InlineKeyboardButton(_("keyboards.inline_keyboards.payment_methods.set_payment_gateway"), callback_data="coming_soon")
        ],
        [
            InlineKeyboardButton(_("keyboards.inline_keyboards.payment_methods.set_crypto"), callback_data="coming_soon")
        ],
        [InlineKeyboardButton(_("keyboards.inline_keyboards.payment_methods.back_to_financial_settings"), callback_data="back_to_financial_settings")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_plan_management_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        # --- FIX: All keys now use the 'keyboards.' namespace ---
        [
            InlineKeyboardButton(_("keyboards.inline_keyboards.plan_management.manage_unlimited"), callback_data="admin_manage_unlimited"),
            InlineKeyboardButton(_("keyboards.inline_keyboards.plan_management.manage_volumetric"), callback_data="admin_manage_volumetric")
        ],
        [
            InlineKeyboardButton(_("keyboards.inline_keyboards.plan_management.set_plan_names"), callback_data="admin_set_plan_names")
        ],
        [
            InlineKeyboardButton(_("keyboards.inline_keyboards.plan_management.back_to_financial_settings"), callback_data="back_to_financial_settings")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_management_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        # --- FIX: All keys now use the 'keyboards.' namespace ---
        [KeyboardButton(_("keyboards.helper_tools.back_to_management_menu"))],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def get_test_account_settings_keyboard() -> InlineKeyboardMarkup:
    bot_settings = await load_bot_settings()
    is_enabled = bot_settings.get('is_test_account_enabled', False)
    
    # --- FIX: All keys now use the 'keyboards.' namespace ---
    toggle_text = _("keyboards.inline_keyboards.test_account_settings.disable") if is_enabled else _("keyboards.inline_keyboards.test_account_settings.enable")
    toggle_callback = "admin_test_acc_disable" if is_enabled else "admin_test_acc_enable"
    
    keyboard = [
        [
            InlineKeyboardButton(toggle_text, callback_data=toggle_callback)
        ],
        [
            InlineKeyboardButton(_("keyboards.inline_keyboards.test_account_settings.set_volume"), callback_data="admin_test_acc_set_gb"),
            InlineKeyboardButton(_("keyboards.inline_keyboards.test_account_settings.set_duration"), callback_data="admin_test_acc_set_hours")
        ],
        [
            InlineKeyboardButton(_("keyboards.inline_keyboards.test_account_settings.set_limit"), callback_data="admin_test_acc_set_limit")
        ],
        [
            InlineKeyboardButton(_("keyboards.inline_keyboards.test_account_settings.back_to_tools"), callback_data="admin_test_acc_back")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_connection_guide_keyboard() -> InlineKeyboardMarkup:
    """
    Creates an inline keyboard with a single button to show connection guides.
    """
    keyboard = [
        [
            InlineKeyboardButton(
                _("keyboards.inline_keyboards.general.connection_guide"), 
                callback_data="show_connection_guides"
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(_("keyboards.helper_tools.back_to_settings"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- ✨ NEW FUNCTION ADDED HERE ✨ ---
def get_balance_management_keyboard() -> ReplyKeyboardMarkup:
    """
    Creates a dedicated ReplyKeyboard for the balance management conversation.
    This allows for a quick exit from the conversation.
    """
    keyboard = [
        [KeyboardButton(_("keyboards.financials.balance_management_back_button"))]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
# --- ✨ END OF NEW FUNCTION ✨ ---
