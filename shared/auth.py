# FILE: shared/auth.py (FINAL VERSION WITH FORCED JOIN DECORATOR)

from functools import wraps
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler
from telegram import error
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
    from shared.callbacks import admin_fallback_reroute, end_conversation_and_show_menu

    admin_menu_buttons = [
        _("keyboards.admin_main_menu.user_management"),
        _("keyboards.admin_main_menu.settings_and_tools"),
        _("keyboards.admin_main_menu.notes_management"),
        _("keyboards.admin_main_menu.send_message"),
        _("keyboards.admin_main_menu.customer_panel_view"),
        _("keyboards.admin_main_menu.guides_settings")
    ]
    valid_buttons = [btn for btn in admin_menu_buttons if btn]
    ADMIN_MAIN_MENU_REGEX = r'^(' + '|'.join(valid_buttons) + r')$'
    
    return [
        MessageHandler(filters.Regex(ADMIN_MAIN_MENU_REGEX), admin_fallback_reroute),
        CommandHandler('cancel', end_conversation_and_show_menu)
    ]

ADMIN_CONV_FALLBACKS = get_admin_fallbacks()


# (✨ NEW SECTION) Forced Join Channel Decorator
# =============================================================================
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.db_manager import load_bot_settings, load_forced_join_channel
from telegram.error import BadRequest, Forbidden

def _create_join_channel_keyboard(channel_username: str) -> InlineKeyboardMarkup:
    """Creates the keyboard for the user to join the channel."""
    keyboard = [
        [InlineKeyboardButton(_("keyboards.forced_join.join_channel_button"), url=f"https://t.me/{channel_username}")],
        [InlineKeyboardButton(_("keyboards.forced_join.check_membership_button"), callback_data="check_join_status")]
    ]
    return InlineKeyboardMarkup(keyboard)

def ensure_channel_membership(func):
    """
    Decorator for handlers (like /start) to enforce channel membership.
    1. Checks if the feature is enabled in bot settings.
    2. Checks if a channel username is configured.
    3. Checks the user's membership status in that channel.
    If the user is not a member, it sends a message with a join button.
    """
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        # Skip check for admins
        if await is_admin(user.id):
            return await func(update, context, *args, **kwargs)

        settings = await load_bot_settings()
        is_enabled = settings.get('is_forced_join_active', False)
        
        # If the feature is disabled, proceed to the original function
        if not is_enabled:
            return await func(update, context, *args, **kwargs)

        channel_username = await load_forced_join_channel()
        
        # If no channel is set, proceed to the original function
        if not channel_username:
            LOGGER.warning("Forced join is active, but no channel username is configured.")
            return await func(update, context, *args, **kwargs)

        try:
            member = await context.bot.get_chat_member(chat_id=f"@{channel_username}", user_id=user.id)
            
            # If user is a member, creator, or admin, let them pass
            if member.status in ['member', 'administrator', 'creator']:
                return await func(update, context, *args, **kwargs)

        except (BadRequest, Forbidden) as e:
            # BadRequest: Channel not found. Forbidden: Bot is not an admin in the channel.
            LOGGER.error(f"Error checking membership for @{channel_username}: {e}. Disabling check temporarily for this user.")
            # Let the user pass but log the critical error for the admin
            return await func(update, context, *args, **kwargs)

        # If the user is not a member (e.g., status is 'left' or 'kicked')
        message_text = _("general.forced_join_message", channel=f"@{channel_username}")
        keyboard = _create_join_channel_keyboard(channel_username)
        
        target_message = update.effective_message
        if update.callback_query:
            # If this was triggered by "Check Membership", edit the original message
            await update.callback_query.answer(_("general.errors.not_joined_yet"), show_alert=True)
            try:
                await target_message.edit_text(text=message_text, reply_markup=keyboard, parse_mode='HTML')
            except error.BadRequest as e:
                if "Message is not modified" not in str(e): # Avoid error on no change
                    # If editing fails, send a new message
                    await context.bot.send_message(chat_id=user.id, text=message_text, reply_markup=keyboard, parse_mode='HTML')
        else: # If triggered by /start
            await target_message.reply_html(text=message_text, reply_markup=keyboard)

    return wrapped