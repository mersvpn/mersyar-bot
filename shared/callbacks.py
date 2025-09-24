# FILE: shared/callbacks.py (REFACTORED TO BREAK CIRCULAR IMPORT)

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from .keyboards import get_helper_tools_keyboard
from shared.translator import _ # Import translator

LOGGER = logging.getLogger(__name__)


async def admin_fallback_reroute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles admin main menu button presses during a conversation to gracefully
    exit the conversation and navigate to the requested menu.
    MOVED HERE TO BREAK A CIRCULAR IMPORT between general/actions and auth.
    """
    # Local import to avoid its own circular dependencies
    from modules.marzban.handler import show_user_management_menu
    from modules.financials.handler import show_financial_menu # Corrected function name
    from modules.general.actions import start
    
    user = update.effective_user
    text = update.message.text
    LOGGER.info(f"--- [Admin Fallback] Admin {user.id} triggered reroute with '{text}'. Ending conversation. ---")
    
    # Using translation keys for robust matching
    user_management_text = _("keyboards.admin_main_menu.manage_users")
    financial_settings_text = _("keyboards.admin_main_menu.financial_settings")
    
    if text == user_management_text:
        await show_user_management_menu(update, context)
    elif text == financial_settings_text:
        await show_financial_menu(update, context)
    else: 
        await start(update, context) # Default fallback
    
    # Clear user_data after rerouting to ensure clean state for next conversation
    context.user_data.clear()
    return ConversationHandler.END

# FILE: shared/callbacks.py
# ADD THIS FUNCTION:

async def end_conversation_and_show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    A generic fallback that cancels any conversation and shows the main menu.
    MOVED HERE TO BREAK A CIRCULAR IMPORT.
    """
    from modules.general.actions import send_main_menu # Local import

    LOGGER.info(f"--- Fallback triggered for user {update.effective_user.id}. Ending conversation. ---")
    context.user_data.clear()
    await send_main_menu(update, context, message_text=_("general.operation_cancelled"))
    return ConversationHandler.END


async def cancel_to_helper_tools(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels a conversation and returns the user to the helper tools menu."""
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
    """Shows a 'Coming Soon' alert to the user for features not yet implemented."""
    query = update.callback_query
    if query:
        # Using translator for the message
        await query.answer(text=_("general.coming_soon"), show_alert=True)