# FILE: modules/customer/actions/panel.py
# (A new file to handle the customer panel)

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

async def show_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays an inline keyboard with purchase and receipt submission options.
    """
    keyboard = [
        [InlineKeyboardButton("🛍️ درخواست خرید اشتراک", callback_data="start_purchase_flow")],
        [InlineKeyboardButton("💳 ارسال رسید پرداخت", callback_data="start_receipt_upload")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="close_customer_panel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text="*به پنل خرید و پرداخت خوش آمدید.*\nلطفاً گزینه مورد نظر خود را انتخاب کنید:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def close_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Closes the inline customer panel message.
    """
    query = update.callback_query
    await query.answer()
    await query.message.delete()