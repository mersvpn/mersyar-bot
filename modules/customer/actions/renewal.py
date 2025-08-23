# ===== IMPORTS & DEPENDENCIES =====
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# --- Local Imports ---
from config import config
from modules.marzban.actions.data_manager import save_non_renewal_users, load_non_renewal_users, normalize_username

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# ===== ACTION FUNCTIONS =====
async def handle_renewal_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles 'Renew Subscription' button click from a customer.
    It notifies all admins and then edits the original message to show a confirmation.
    """
    query = update.callback_query
    # We answer the query immediately to stop the loading animation on the button
    await query.answer()

    user = update.effective_user
    marzban_username = query.data.split('_')[-1] # customer_renew_request_{username}
    normalized_user = normalize_username(marzban_username)

    if config.AUTHORIZED_USER_IDS:
        user_info = f"کاربر {user.full_name}"
        if user.username:
            user_info += f" (@{user.username})"
        user_info += f"\nUser ID: `{user.id}`"

        message_to_admin = (
            f"🔔 **درخواست تمدید اشتراک** 🔔\n\n"
            f"{user_info}\n"
            f"نام کاربری در پنل: `{normalized_user}`\n\n"
            "این کاربر قصد تمدید اشتراک خود را دارد."
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔄 تمدید هوشمند برای {normalized_user}", callback_data=f"renew_{normalized_user}")]
        ])

        num_sent = 0
        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message_to_admin,
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
                num_sent += 1
            except Exception as e:
                LOGGER.error(f"Failed to send renewal notification to admin {admin_id} for user {normalized_user}: {e}", exc_info=True)
        
        # --- START OF FIX: Edit the original message after processing ---
        if num_sent > 0:
            confirmation_text = "✅ درخواست تمدید شما با موفقیت برای پشتیبانی ارسال شد. لطفاً منتظر بمانید."
        else:
            confirmation_text = "❌ مشکلی در ارسال درخواست رخ داد. لطفاً با پشتیبانی تماس بگیرید."
            
        await query.edit_message_text(text=confirmation_text)
        # --- END OF FIX ---

async def handle_do_not_renew(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles 'Do Not Renew' button click, adding the user to the non-renewal list.
    """
    query = update.callback_query
    await query.answer()

    marzban_username = query.data.split('_')[-1] # customer_do_not_renew_{username}
    normalized_user = normalize_username(marzban_username)
    user = update.effective_user

    LOGGER.info(f"User {user.id} ({normalized_user}) opted out of renewal reminders.")

    # Use the centralized async data_manager
    users_list = await load_non_renewal_users()
    if normalized_user not in users_list:
        users_list.append(normalized_user)
        await save_non_renewal_users(users_list)

    await query.edit_message_text(
        "✅ درخواست شما ثبت شد.\n\n"
        "دیگر پیام یادآور تمدید برای این اشتراک دریافت نخواهید کرد."
    )

    # Notify admins about this action
    if config.AUTHORIZED_USER_IDS:
        user_info = f"کاربر {user.full_name}"
        if user.username:
            user_info += f" (@{user.username})"

        message_to_admin = (
            f"ℹ️ **اطلاع‌رسانی عدم تمدید** ℹ️\n\n"
            f"{user_info}\n"
            f"نام کاربری در پنل: `{normalized_user}`\n\n"
            "این کاربر اعلام کرد که **تمایلی به تمدید ندارد**."
        )

        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message_to_admin,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                LOGGER.error(f"Failed to send 'do not renew' notification to admin {admin_id} for user {normalized_user}: {e}", exc_info=True)