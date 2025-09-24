# FILE: modules/auth.py (REFACTORED TO BREAK CIRCULAR IMPORT)

from functools import wraps
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler

from config import config
from shared.translator import _ # Import translator

LOGGER = logging.getLogger(__name__)


async def is_admin(user_id: int) -> bool:
    """A simple, reusable check if a user is an admin."""
    return user_id in config.AUTHORIZED_USER_IDS

def admin_only(func):
    """Decorator for standard handlers (non-conversation)."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not await is_admin(user.id):
            LOGGER.warning(f"Unauthorized access denied for {user.id if user else 'Unknown'} in '{func.__name__}'.")
            if update.message:
                await update.message.reply_text(_("errors.admin_only_command"))
            elif update.callback_query:
                await update.callback_query.answer(_("errors.admin_only_callback"), show_alert=True)
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

def admin_only_conv(func):
    """Decorator for CONVERSATION HANDLER entry points."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or not await is_admin(user.id):
            LOGGER.warning(f"Unauthorized access for {user.id if user else 'Unknown'} to conv '{func.__name__}'.")
            if update.message:
                await update.message.reply_text(_("errors.admin_only_section"))
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapped


def get_admin_fallbacks():
    """
    Returns a list of shared fallback handlers for admin conversations.
    This structure prevents circular import errors.
    """
    # (⭐ FIX ⭐) Import is now from the central, safe location.
    from shared.callbacks import admin_fallback_reroute
    from shared.callbacks import admin_fallback_reroute, end_conversation_and_show_menu

    
    # Use translator for robust regex matching
    admin_menu_buttons = [
        _("keyboards.admin_main_menu.manage_users"),
        _("keyboards.admin_main_menu.financial_settings"),
        _("keyboards.admin_main_menu.note_management"),
        _("keyboards.admin_main_menu.send_message"),
        _("keyboards.admin_main_menu.customer_panel"),
        _("keyboards.admin_main_menu.guides_settings"),
        _("keyboards.admin_main_menu.back_to_main") # This key might not exist, adjust as needed
    ]
    # Filter out any potential empty strings if a key is missing
    valid_buttons = [btn for btn in admin_menu_buttons if btn]
    ADMIN_MAIN_MENU_REGEX = r'^(' + '|'.join(valid_buttons) + r')$'
    
    return [
        MessageHandler(filters.Regex(ADMIN_MAIN_MENU_REGEX), admin_fallback_reroute),
        CommandHandler('cancel', end_conversation_and_show_menu)
    ]

ADMIN_CONV_FALLBACKS = get_admin_fallbacks()