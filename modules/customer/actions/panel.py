# FILE: modules/customer/actions/panel.py (REVISED)

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# --- REVISED: Removed unnecessary import ---
from shared.keyboards import get_customer_purchase_menu_keyboard
from modules.general.actions import send_main_menu

async def show_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    منوی اصلی خرید و پرداخت مشتری را نمایش می‌دهد.
    """
    # --- REVISED: Added 'await' as the keyboard function is now async ---
    reply_markup = await get_customer_purchase_menu_keyboard()
    
    text = "🛍️ *فــــــــــروشـــــــــــگاه*\n\nاز این بخش می‌توانید سرویس جدید سفارش دهید یا رسید پرداخت خود را ارسال کنید."
    
    query = update.callback_query
    if query:
        # This case is now less likely to happen as there is no 'back' button to this menu
        # but we keep it for robustness.
        await query.answer()
        await query.edit_message_text(
            text=text, 
            reply_markup=reply_markup, 
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # This is the primary entry point from the main menu button
        await update.message.reply_text(
            text=text, 
            reply_markup=reply_markup, 
            parse_mode=ParseMode.MARKDOWN
        )

# --- REMOVED: The show_plan_type_menu function is no longer needed ---

async def close_customer_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    پنل خرید مشتری را می‌بندد (حذف پیام).
    """
    query = update.callback_query
    await query.answer()
    # Deleting the message is a cleaner UX than editing it to say "you returned"
    await query.message.delete()