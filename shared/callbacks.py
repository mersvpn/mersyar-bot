# ===== IMPORTS & DEPENDENCIES =====
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

# --- Local Imports ---
# Import the keyboard function here to avoid circular imports in other files
from .keyboards import get_admin_main_menu_keyboard

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# ===== GENERIC CALLBACKS =====

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    A generic fallback function to cancel any admin conversation and return to the main menu.
    """
    LOGGER.debug(f"Conversation cancelled by user {update.effective_user.id}")
    context.user_data.clear()

    message_text = "عملیات لغو شد."
    target_message = update.message or (update.callback_query and update.callback_query.message)

    if update.callback_query:
        await update.callback_query.answer()
        try:
            # Try to delete the message to clean up the chat interface
            await update.callback_query.message.delete()
        except Exception as e:
            LOGGER.warning(f"Could not delete message on cancel: {e}")

    # Send a new message with the main menu to ensure the user isn't stuck
    await context.bot.send_message(
        chat_id=target_message.chat_id,
        text=f"{message_text}\nبه منوی اصلی بازگشتید.",
        reply_markup=get_admin_main_menu_keyboard()
    )
    return ConversationHandler.END