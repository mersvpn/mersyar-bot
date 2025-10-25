# FILE: shared/auth.py (REVISED TO BREAK CIRCULAR DEPENDENCY)

from functools import wraps
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler
from telegram import error, InlineKeyboardButton, InlineKeyboardMarkup
from config import config
from shared.translator import _

LOGGER = logging.getLogger(__name__)

async def is_admin(user_id: int) -> bool:
    """A simple, reusable check if a user is an admin."""
    return user_id in config.AUTHORIZED_USER_IDS

def admin_only(func):
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
    Returns a list of fallback handlers for admin conversations.
    This function should be called at RUNTIME, not import time.
    """
    from shared.callbacks import admin_fallback_reroute, end_conversation_and_show_menu
    
    # Translate keys only when the function is called
    admin_menu_buttons = [
        _("keyboards.admin_main_menu.manage_users"),
        _("keyboards.admin_main_menu.settings_and_tools"),
        _("keyboards.admin_main_menu.daily_notes"), # Corrected key
        _("keyboards.admin_main_menu.send_message"),
        _("keyboards.admin_main_menu.customer_panel_view"),
        _("keyboards.admin_main_menu.guides_settings")
    ]
    
    # Filter out any potential None values if a key is missing, although it shouldn't happen now
    valid_buttons = [btn for btn in admin_menu_buttons if btn]
    admin_main_menu_filter = filters.Text(valid_buttons)

    return [
        MessageHandler(admin_main_menu_filter, admin_fallback_reroute),
        CommandHandler('cancel', end_conversation_and_show_menu)
    ]

# The problematic constant has been removed.
# ADMIN_CONV_FALLBACKS = get_admin_fallbacks() # <--- THIS LINE IS DELETED

def _create_join_channel_keyboard(channel_username: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(_("keyboards.forced_join.join_channel_button"), url=f"https://t.me/{channel_username}")],
        [InlineKeyboardButton(_("keyboards.forced_join.check_membership_button"), callback_data="check_join_status")]
    ]
    return InlineKeyboardMarkup(keyboard)

def ensure_channel_membership(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        from database.crud import bot_setting as crud_bot_setting
        user = update.effective_user
        if not user:
            return

        if await is_admin(user.id):
            return await func(update, context, *args, **kwargs)

        settings = await crud_bot_setting.load_bot_settings()
        is_enabled = settings.get('is_forced_join_active', False)
        
        if not is_enabled:
            return await func(update, context, *args, **kwargs)

        channel_username = settings.get('forced_join_channel')
        
        if not channel_username:
            LOGGER.warning("Forced join is active, but no channel username is configured.")
            return await func(update, context, *args, **kwargs)

        try:
            member = await context.bot.get_chat_member(chat_id=f"@{channel_username}", user_id=user.id)
            if member.status in ['member', 'administrator', 'creator']:
                return await func(update, context, *args, **kwargs)
        except (error.BadRequest, error.Forbidden) as e:
            LOGGER.error(f"Error checking membership for @{channel_username}: {e}. Disabling check temporarily for this user.")
            return await func(update, context, *args, **kwargs)

        message_text = _("general.forced_join_message", channel=f"@{channel_username}")
        keyboard = _create_join_channel_keyboard(channel_username)
        
        target_message = update.effective_message
        if update.callback_query:
            await update.callback_query.answer(_("general.errors.not_joined_yet"), show_alert=True)
            try:
                await target_message.edit_text(text=message_text, reply_markup=keyboard, parse_mode='HTML')
            except error.BadRequest as e:
                if "Message is not modified" not in str(e):
                    await context.bot.send_message(chat_id=user.id, text=message_text, reply_markup=keyboard, parse_mode='HTML')
        else:
            await target_message.reply_html(text=message_text, reply_markup=keyboard)

    return wrapped

async def is_user_admin(user_id: int) -> bool:
    return user_id in config.AUTHORIZED_USER_IDS
