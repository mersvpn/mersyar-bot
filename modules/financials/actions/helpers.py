# ===== IMPORTS & DEPENDENCIES =====
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from modules.marzban.actions.data_manager import load_financials

# ===== UI HELPER FUNCTIONS for Financial Module =====

async def format_financial_info_message() -> str:
    """
    Asynchronously loads financial data and formats it into a user-friendly message.
    """
    financials = await load_financials()

    # Use .get() with a default value for safety.
    account_holder = financials.get("account_holder", "تنظیم نشده")
    card_number = financials.get("card_number", "تنظیم نشده")
    extra_text = financials.get("extra_text", "راهنمای پرداخت")

    message = (
        "**💰 تنظیمات مالی**\n\n"
        "از این بخش می‌توانید اطلاعات پرداخت را برای نمایش به مشتریان مدیریت کنید.\n\n"
        "**اطلاعات فعلی:**\n"
        f"▫️ **نام صاحب حساب:** `{account_holder}`\n"
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
        [
            InlineKeyboardButton("💬 ویرایش متن دلخواه", callback_data="fin_edit_text")
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)