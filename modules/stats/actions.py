# FILE: modules/stats/actions.py (NEW FILE)

import time
import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db_manager import get_total_users_count
from modules.auth import admin_only

LOGGER = logging.getLogger(__name__)

async def _calculate_ping(context: ContextTypes.DEFAULT_TYPE) -> float:
    """Calculates the ping to Telegram API by sending a simple request."""
    start_time = time.monotonic()
    try:
        # get_me is a lightweight request perfect for ping calculation
        await context.bot.get_me()
        end_time = time.monotonic()
        # Return ping in milliseconds
        return (end_time - start_time) * 1000
    except Exception as e:
        LOGGER.error(f"Could not calculate ping: {e}")
        return -1 # Return -1 to indicate an error

@admin_only
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gathers and displays bot statistics to the admin."""
    message = await update.message.reply_text("📊 در حال جمع‌آوری آمار...")

    # ۱. دریافت تعداد کل کاربران
    total_users = await get_total_users_count()

    # ۲. محاسبه پینگ
    ping_ms = await _calculate_ping(context)
    ping_text = f"{ping_ms:.2f} میلی‌ثانیه" if ping_ms != -1 else "ناموفق"
    
    # ۳. ساخت پیام نهایی
    stats_text = (
        f"📊 **آمار کلی ربات**\n\n"
        f"👥 **تعداد کل کاربران:** {total_users} نفر\n"
        f"⚡️ **پینگ به سرور تلگرام:** {ping_text}"
    )

    await message.edit_text(stats_text, parse_mode=ParseMode.MARKDOWN)