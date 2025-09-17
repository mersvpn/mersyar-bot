# FILE: modules/stats/actions.py (REVISED FOR I18N)

import time
import logging
import subprocess
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db_manager import get_total_users_count
from modules.auth import admin_only

LOGGER = logging.getLogger(__name__)

def _get_bot_version() -> str:
    """Fetches the latest Git tag to determine the bot's version automatically."""
    from shared.translator import _
    try:
        git_command = ["git", "describe", "--tags", "--abbrev=0"]
        result = subprocess.run(
            git_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        LOGGER.warning("Could not automatically determine bot version from Git tag.")
        return _("stats.version_not_available")

async def _calculate_ping(context: ContextTypes.DEFAULT_TYPE) -> float:
    """Calculates the ping to Telegram API by sending a simple request."""
    start_time = time.monotonic()
    try:
        await context.bot.get_me()
        end_time = time.monotonic()
        return (end_time - start_time) * 1000
    except Exception as e:
        LOGGER.error(f"Could not calculate ping: {e}")
        return -1

@admin_only
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gathers and displays bot statistics to the admin."""
    from shared.translator import _
    message = await update.message.reply_text(_("stats.gathering"))

    total_users = await get_total_users_count()

    ping_ms = await _calculate_ping(context)
    ping_text = _("stats.ping_ms", ms=ping_ms) if ping_ms != -1 else _("stats.ping_failed")
    
    bot_version = _get_bot_version()

    stats_text = _("stats.title")
    stats_text += _("stats.version", version=f"`{bot_version}`")
    stats_text += _("stats.total_users", count=total_users)
    stats_text += _("stats.ping_to_telegram", ping=ping_text)

    await message.edit_text(stats_text, parse_mode=ParseMode.MARKDOWN)