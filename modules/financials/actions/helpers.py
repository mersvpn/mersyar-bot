# ===== IMPORTS & DEPENDENCIES =====
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from modules.marzban.actions.data_manager import load_financials

# ===== UI HELPER FUNCTIONS for Financial Module =====

async def format_financial_info_message() -> str:
    """
    Asynchronously loads financial data and formats it into a user-friendly message.
    """
    financials = await crud_financial.get_financial_settings()

    # --- FIX: Changed 'account_holder' to 'card_holder' to match the database schema ---
    card_holder = financials.get("card_holder", "تنظیم نشده")
    card_number = financials.get("card_number", "تنظیم نشده")
    # Note: 'extra_text' is not stored in the database, so it will always be the default.
    extra_text = "راهنمای پرداخت"

    message = (
        "**💰 تنظیمات مالی**\n\n"
        "از این بخش می‌توانید اطلاعات پرداخت را برای نمایش به مشتریان مدیریت کنید.\n\n"
        "**اطلاعات فعلی:**\n"
        f"▫️ **نام صاحب حساب:** `{card_holder}`\n"
        f"▫️ **شماره کارت:** `{card_number}`\n"
        f"▫️ **متن دلخواه:** _{extra_text}_\n\n"
        "لطفاً بخش مورد نظر برای ویرایش را انتخاب کنید:"
    )
    return message

def build_financial_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Builds the static inline keyboard for the financial settings menu.
    """
    keyboard = [
        [
            InlineKeyboardButton("✏️ ویرایش نام", callback_data="fin_edit_holder"),
            InlineKeyboardButton("💳 ویرایش شماره کارت", callback_data="fin_edit_card")
        ],
        # The button for 'extra_text' is removed as it's no longer editable from the DB.
        # [
        #     InlineKeyboardButton("💬 ویرایش متن دلخواه", callback_data="fin_edit_text")
        # ],
        [
            InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)