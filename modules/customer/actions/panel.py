# FILE: modules/customer/actions/panel.py (REVISED FOR REPLY KEYBOARD SHOP)

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# --- REVISED: Import the new shop keyboard ---
from shared.keyboards import get_customer_shop_keyboard

async def show_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays the main customer shop menu using a ReplyKeyboardMarkup.
    """
    reply_markup = get_customer_shop_keyboard()
    
    text = "🛍️ *فــــــــــروشـــــــــــگاه*\n\nاز این بخش می‌توانید سرویس جدید سفارش دهید یا رسید پرداخت خود را ارسال کنید."
    
    await update.message.reply_text(
        text=text, 
        reply_markup=reply_markup, 
        parse_mode=ParseMode.MARKDOWN
    )

# --- REMOVED: The close_customer_panel function is no longer needed. ---
# The 'Back' button will be handled by a general handler.