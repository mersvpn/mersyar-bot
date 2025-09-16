# FILE: modules/customer/actions/panel.py (REVISED FOR I18N)

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from shared.keyboards import get_customer_shop_keyboard
from shared.translator import _

async def show_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays the main customer shop menu using a ReplyKeyboardMarkup.
    """
    reply_markup = get_customer_shop_keyboard()
    text = _("customer_panel.shop_welcome")
    
    # The message can come from a button click (message) or callback (callback_query.message)
    target_message = update.effective_message
    
    await target_message.reply_text(
        text=text, 
        reply_markup=reply_markup, 
        parse_mode=ParseMode.MARKDOWN
    )