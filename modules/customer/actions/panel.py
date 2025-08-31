# FILE: modules/customer/actions/panel.py
# (نسخه نهایی با قابلیت ویرایش پیام برای بازگشت)

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram import error

async def show_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays or edits an inline keyboard with purchase and receipt submission options.
    """
    keyboard = [
        [InlineKeyboardButton("🛍️ درخواست خرید اشتراک", callback_data="start_purchase_flow")],
        [InlineKeyboardButton("💳 ارسال رسید پرداخت", callback_data="start_receipt_upload")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="close_customer_panel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "*به پنل خرید و پرداخت خوش آمدید.*\nلطفاً گزینه مورد نظر خود را انتخاب کنید:"
    
    query = update.callback_query
    if query:
        # If called from a back button, edit the message
        await query.answer()
        await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        # If called from the main menu, send a new message
        await update.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)


async def close_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Closes the inline customer panel message.
    """
    query = update.callback_query
    await query.answer()
    await query.message.delete()