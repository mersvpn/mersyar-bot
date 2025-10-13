# --- START OF FILE shared/log_channel.py (REVISED) ---

# FILE: shared/log_channel.py (REVISED FOR STABILITY)

import logging
import html
from telegram import Bot, User
from telegram.constants import ParseMode
from telegram.error import TelegramError

# --- MODIFIED IMPORT ---
from database.crud import bot_setting as crud_bot_setting
# --- ----------------- ---
from shared.translator import _

LOGGER = logging.getLogger(__name__)

async def send_log(bot: Bot, text: str, parse_mode: str = ParseMode.HTML) -> bool:
    """
    Sends a log message to the configured log channel if it's enabled.
    Uses HTML as the default parse mode for better stability.

    Args:
        bot: The bot instance from context.bot.
        text: The message text to send.
        parse_mode: The parse mode for the message.

    Returns:
        True if the message was sent successfully, False otherwise.
    """
    try:
        settings = await crud_bot_setting.load_bot_settings()
        
        is_enabled = settings.get('is_log_channel_enabled', False)
        channel_id = settings.get('log_channel_id')

        if not is_enabled:
            LOGGER.debug("Log channel is disabled. Skipping log.")
            return False

        if not channel_id:
            LOGGER.warning("Log channel is enabled but no channel ID is set. Skipping log.")
            return False

        await bot.send_message(
            chat_id=channel_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=True
        )
        LOGGER.info(f"Successfully sent log to channel {channel_id}")
        return True

    except TelegramError as e:
        LOGGER.error(f"Failed to send log to channel. Telegram Error: {e}")
        return False
    except Exception as e:
        LOGGER.error(f"An unexpected error occurred in send_log: {e}", exc_info=True)
        return False

async def log_new_user_joined(bot: Bot, user: User) -> None:
    """Sends a notification to the log channel when a new user starts the bot."""

    # Sanitize user inputs for HTML parse mode
    first_name = html.escape(user.first_name)
    username_text = f"(@{user.username})" if user.username else _("log_channel.no_username")
    
    # Use HTML tags for formatting
    log_text = _("log_channel.new_user_joined_html",
                 first_name=f"<b>{first_name}</b>",
                 user_id=f"<code>{user.id}</code>",
                 username=username_text)
    
    # We call the main send_log function. It will now use HTML by default.
    await send_log(bot, log_text)

# --- END OF FILE shared/log_channel.py (REVISED) ---