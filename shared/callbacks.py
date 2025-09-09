# FILE: shared/callbacks.py (REVISED)

# ===== IMPORTS & DEPENDENCIES =====
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

# --- Local Imports ---
from .keyboards import get_helper_tools_keyboard

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# ===== GENERIC CALLBACKS =====

# NOTE: The old `cancel_conversation` function has been REMOVED.
# We will now use the central fallback function located in `modules/general/actions.py`
# which is `end_conversation_and_show_menu`. This prevents duplicate messages.


async def cancel_to_helper_tools(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Cancels a conversation and returns the user to the helper tools menu.
    """
    LOGGER.debug(f"Conversation cancelled by user {update.effective_user.id}, returning to helper tools.")
    context.user_data.clear()

    message_text = "عملیات لغو شد."
    target_message = update.message or (update.callback_query and update.callback_query.message)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.message.delete()
        except Exception as e:
            LOGGER.warning(f"Could not delete message on cancel: {e}")
    
    await context.bot.send_message(
        chat_id=target_message.chat_id,
        text=f"{message_text}\nبه منوی ابزارهای کمکی بازگشتید.",
        reply_markup=get_helper_tools_keyboard()
    )
    return ConversationHandler.END


async def show_coming_soon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Shows a 'Coming Soon' alert to the user for features not yet implemented.
    This is used for placeholder buttons.
    """
    query = update.callback_query
    if query:
        await query.answer(text="⏳ این قابلیت به زودی اضافه خواهد شد.", show_alert=True)