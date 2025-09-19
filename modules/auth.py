# FILE: modules/auth.py (FINAL, WITH CIRCULAR IMPORT FIX)

from functools import wraps
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler

from config import config
# Note: We remove the top-level import of general.actions to break the cycle.

LOGGER = logging.getLogger(__name__)

# =============================================================================
#  1. Authorization Decorators
# =============================================================================

def admin_only(func):
    """Decorator for standard handlers (non-conversation)."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id not in config.AUTHORIZED_USER_IDS:
            LOGGER.warning(f"Unauthorized access denied for {user.id if user else 'Unknown'} in '{func.__name__}'.")
            if update.message:
                await update.message.reply_text("⛔️ شما اجازه دسترسی به این دستور را ندارید.")
            elif update.callback_query:
                await update.callback_query.answer("⛔️ شما اجازه دسترسی ندارید.", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)
    return wrapped


def admin_only_conv(func):
    """Decorator for CONVERSATION HANDLER entry points."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id not in config.AUTHORIZED_USER_IDS:
            LOGGER.warning(f"Unauthorized access for {user.id if user else 'Unknown'} to conv '{func.__name__}'.")
            if update.message:
                await update.message.reply_text("⛔️ شما اجازه دسترسی به این بخش را ندارید.")
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapped

# =============================================================================
#  2. Shared Conversation Fallbacks for Admins
# =============================================================================

def get_admin_fallbacks():
    """
    Returns a list of shared fallback handlers for admin conversations.
    We use a function to do a local import, breaking the circular dependency.
    """
    from modules.general.actions import admin_fallback_reroute, end_conversation_and_show_menu
    
    ADMIN_MAIN_MENU_REGEX = r'^(👤 مدیریت کاربران|⚙️ تنظیمات و ابزارها|📓 مدیریت یادداشت‌ها|📨 ارسال پیام|💻 ورود به پنل کاربری|📚 تنظیمات آموزش|🔙 بازگشت به منوی اصلی)$'
    
    return [
        MessageHandler(filters.Regex(ADMIN_MAIN_MENU_REGEX), admin_fallback_reroute),
        CommandHandler('cancel', end_conversation_and_show_menu)
    ]

# For convenience, you can still have a top-level variable if needed elsewhere
ADMIN_CONV_FALLBACKS = get_admin_fallbacks()