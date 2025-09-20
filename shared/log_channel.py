# FILE: shared/log_channel.py (NEW FILE)

import logging
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from database.db_manager import load_bot_settings

LOGGER = logging.getLogger(__name__)

async def send_log(bot: Bot, text: str, parse_mode: str = ParseMode.MARKDOWN_V2) -> bool:
    """
    Sends a log message to the configured log channel if it's enabled.

    Args:
        bot: The bot instance from context.bot.
        text: The message text to send.
        parse_mode: The parse mode for the message.

    Returns:
        True if the message was sent successfully, False otherwise.
    """
    try:
        settings = await load_bot_settings()
        
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
    
    # کد جدید برای افزودن به انتهای فایل
from telegram import User

async def log_new_user_joined(bot: Bot, user: User) -> None:
    """Sends a notification to the log channel when a new user starts the bot."""
    from shared.translator import _

    # Sanitize user inputs for MarkdownV2
    first_name = user.first_name.replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]')
    username_text = f"\\(@{user.username}\\)" if user.username else _("log_channel.no_username")

    log_text = _("log_channel.new_user_joined",
                 first_name=first_name,
                 user_id=user.id,
                 username=username_text)
    
    # We call the main send_log function to handle the sending logic
    await send_log(bot, log_text, parse_mode=ParseMode.MARKDOWN_V2)