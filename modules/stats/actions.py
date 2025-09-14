# FILE: modules/stats/actions.py (REVISED FOR AUTO-VERSIONING)

import time
import logging
import subprocess  # <-- NEW IMPORT
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db_manager import get_total_users_count
from modules.auth import admin_only

LOGGER = logging.getLogger(__name__)


def _get_bot_version() -> str:
    """
    Fetches the latest Git tag to determine the bot's version automatically.
    Returns a version string (e.g., 'v1.5.4') or 'N/A' on failure.
    """
    try:
        # This command gets the most recent tag on the current branch.
        # It's lightweight and perfect for versioning.
        git_command = ["git", "describe", "--tags", "--abbrev=0"]
        
        # Execute the command
        result = subprocess.run(
            git_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # To get output as a string
            check=True  # To raise an exception if the command fails
        )
        
        # Return the version, stripping any leading/trailing whitespace
        return result.stdout.strip()
        
    except (subprocess.CalledProcessError, FileNotFoundError):
        # CalledProcessError: The command failed (e.g., no tags exist).
        # FileNotFoundError: Git is not installed or not in PATH.
        LOGGER.warning("Could not automatically determine bot version from Git tag.")
        return "N/A (Git not available)"


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
    message = await update.message.reply_text("📊 در حال جمع‌آوری آمار...")

    # ۱. دریافت تعداد کل کاربران
    total_users = await get_total_users_count()

    # ۲. محاسبه پینگ
    ping_ms = await _calculate_ping(context)
    ping_text = f"{ping_ms:.2f} میلی‌ثانیه" if ping_ms != -1 else "ناموفق"
    
    # ۳. دریافت خودکار نسخه ربات
    bot_version = _get_bot_version()

    # ۴. ساخت پیام نهایی
    stats_text = (
        f"📊 **آمار کلی ربات**\n\n"
        f"⚙️ **نسخه ربات:** `{bot_version}`\n"
        f"👥 **تعداد کل کاربران:** {total_users} نفر\n"
        f"⚡️ **پینگ به سرور تلگرام:** {ping_text}"
    )

    await message.edit_text(stats_text, parse_mode=ParseMode.MARKDOWN)