# FILE: modules/customer/actions/panel.py (نسخه نهایی و اصلاح شده)

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# ایمپورت کردن کیبورد از ماژول اشتراکی
from shared.keyboards import get_customer_purchase_menu_keyboard
# --- FIX: ایمپورت کردن تابع کمکی جدید برای نمایش منوی اصلی ---
from modules.general.actions import send_main_menu

async def show_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    منوی اصلی خرید و پرداخت مشتری را با گزینه‌های جدید نمایش می‌دهد.
    """
    reply_markup = get_customer_purchase_menu_keyboard()
    
    text = "🛍️ *پنل خرید و پرداخت*\n\nاز این بخش می‌توانید سرویس جدید سفارش دهید یا رسید پرداخت خود را ارسال کنید."
    
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            text=text, 
            reply_markup=reply_markup, 
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            text=text, 
            reply_markup=reply_markup, 
            parse_mode=ParseMode.MARKDOWN
        )


async def close_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Closes the customer's purchase panel and returns them to the appropriate main menu.
    """
    query = update.callback_query
    await query.answer()
    
    # --- FIX: Instead of deleting the message, call the central main menu function ---
    # This ensures the admin gets the correct "customer view" keyboard back.
    await send_main_menu(update, context, message_text="به منوی اصلی بازگشتید.")
    # --- END OF FIX ---