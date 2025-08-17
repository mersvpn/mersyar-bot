# ===== IMPORTS & DEPENDENCIES =====
import logging
from telegram import Update
from telegram.ext import ContextTypes

# --- Local Imports ---
from config import config
from modules.marzban.actions.data_manager import load_users_map

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# ===== RECEIPT HANDLING LOGIC =====

async def handle_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles incoming photos from non-admin users, assuming they are payment receipts.
    Forwards the receipt to all admins for verification.
    """
    user = update.effective_user
    # This handler should only react to messages from non-admin users.
    # This check is an extra layer of safety.
    if user.id in config.AUTHORIZED_USER_IDS:
        return

    # Acknowledge receipt to the customer
    await update.message.reply_text(
        "✅ رسید شما دریافت شد و برای بررسی به ادمین ارسال گردید.\n\n"
        "از پرداخت شما متشکریم! لطفاً منتظر تایید ادمین بمانید."
    )

    # --- Prepare information for the admin ---
    user_info = f"👤 **کاربر:** {user.full_name}"
    if user.username:
        user_info += f" (@{user.username})"
    user_info += f"\n🆔 **ID تلگرام:** `{user.id}`"

    # Try to find the associated Marzban username(s)
    users_map = await load_users_map()
    linked_accounts = [username for username, t_id in users_map.items() if t_id == user.id]
    if linked_accounts:
        user_info += "\n"
        user_info += "▫️ **سرویس‌های متصل:**\n"
        for acc in linked_accounts:
            user_info += f"  - `{acc}`\n"

    caption_for_admin = (
        f"🧾 **رسید پرداخت جدید دریافت شد** 🧾\n\n"
        f"{user_info}"
    )

    # --- Forward the photo to all admins ---
    if config.AUTHORIZED_USER_IDS:
        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                # Forward the original message (which contains the photo)
                await context.bot.forward_message(
                    chat_id=admin_id,
                    from_chat_id=user.id,
                    message_id=update.message.message_id
                )
                # Send the user info as a separate message for clarity
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=caption_for_admin,
                    parse_mode='Markdown'
                )
            except Exception as e:
                LOGGER.error(f"Failed to forward receipt from {user.id} to admin {admin_id}: {e}", exc_info=True)