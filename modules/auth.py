# ===== IMPORTS & DEPENDENCIES =====
from functools import wraps
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

# --- Local Imports ---
from config import config

# --- Setup ---
LOGGER = logging.getLogger(__name__)

# ===== AUTHORIZATION DECORATORS =====

def admin_only(func):
    """
    Decorator for standard handlers (non-conversation).
    Restricts access to users whose IDs are in the AUTHORIZED_USER_IDS list.
    """
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id not in config.AUTHORIZED_USER_IDS:
            LOGGER.warning(f"Unauthorized access denied for user {user.id if user else 'Unknown'} in '{func.__name__}'.")

            # Provide feedback to the user that they are not authorized
            if update.message:
                await update.message.reply_text("⛔️ شما اجازه دسترسی به این دستور را ندارید.")
            elif update.callback_query:
                await update.callback_query.answer("⛔️ شما اجازه دسترسی ندارید.", show_alert=True)
            return  # Stop further execution

        return await func(update, context, *args, **kwargs)
    return wrapped


def admin_only_conv(func):
    """
    Decorator for CONVERSATION HANDLER entry points.
    If the user is not an admin, it ends the conversation immediately instead of starting it.
    """
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id not in config.AUTHORIZED_USER_IDS:
            LOGGER.warning(f"Unauthorized access denied for user {user.id if user else 'Unknown'} trying to start conversation '{func.__name__}'.")

            if update.message:
                await update.message.reply_text("⛔️ شما اجازه دسترسی به این بخش را ندارید.")

            return ConversationHandler.END # End the conversation gracefully

        return await func(update, context, *args, **kwargs)
    return wrapped