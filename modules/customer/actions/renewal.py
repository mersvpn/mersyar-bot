# FILE: modules/customer/actions/renewal.py (REVISED FOR I18N AND MARKDOWN SAFETY)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown  # Ensure this import is at the top
from config import config
from modules.marzban.actions.data_manager import normalize_username
from shared.translator import _

LOGGER = logging.getLogger(__name__)

async def handle_renewal_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    marzban_username = query.data.split('_')[-1]
    normalized_user = normalize_username(marzban_username)

    if config.AUTHORIZED_USER_IDS:
        # --- SAFE MARKDOWN V2 ---
        safe_full_name = escape_markdown(user.full_name, version=2)
        user_info = f"کاربر {safe_full_name}"
        if user.username:
            safe_username = escape_markdown(user.username, version=2)
            user_info += f" \\(@{safe_username}\\)"
        user_info += f"\nUser ID: `{user.id}`"

        # ✨✨✨ KEY FIX HERE ✨✨✨
        # The username from Marzban is now also escaped to handle characters like '_'
        safe_normalized_user = escape_markdown(normalized_user, version=2)

        message_to_admin = _("renewal.admin_notification", 
                             user_info=user_info, 
                             username=f"`{safe_normalized_user}`")

        bot_username = context.bot.username
        # Note: URL encoding for usernames in deep links is handled by Telegram,
        # so no escaping is needed for `details_url`.
        details_url = f"https://t.me/{bot_username}?start=details_{normalized_user}"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("buttons.smart_renew_for_user", username=normalized_user), callback_data=f"renew_{normalized_user}")],
            [InlineKeyboardButton(_("buttons.view_user_details"), url=details_url)]
        ])

        num_sent = 0
        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id, text=message_to_admin,
                    reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2
                )
                num_sent += 1
            except Exception as e:
                LOGGER.error(f"Failed to send renewal notification to admin {admin_id} for user {normalized_user}: {e}")
        
        if num_sent > 0:
            confirmation_text = _("renewal.request_sent_success")
        else:
            confirmation_text = _("renewal.request_sent_fail")
            
        await query.edit_message_text(text=confirmation_text, reply_markup=None)
        
    return ConversationHandler.END

async def handle_do_not_renew(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from database.db_manager import add_to_non_renewal_list

    query = update.callback_query
    await query.answer()

    marzban_username = query.data.split('_')[-1]
    normalized_user = normalize_username(marzban_username)
    user = update.effective_user

    LOGGER.info(f"User {user.id} ({normalized_user}) opted out of renewal reminders.")

    await add_to_non_renewal_list(normalized_user)

    await query.edit_message_text(_("renewal.do_not_renew_success"))

    if config.AUTHORIZED_USER_IDS:
        # --- SAFE MARKDOWN (LEGACY) ---
        safe_full_name = escape_markdown(user.full_name, version=1)
        user_info = f"کاربر {safe_full_name}"
        if user.username:
            # Note: No need to escape '@' in legacy markdown
            user_info += f" (@{user.username})"

        # ✨✨✨ SECONDARY FIX HERE ✨✨✨
        # Also escape the Marzban username for this notification
        safe_normalized_user = escape_markdown(normalized_user, version=1)

        message_to_admin = _("renewal.do_not_renew_admin_notification", 
                             user_info=user_info, 
                             username=f"`{safe_normalized_user}`")

        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id, text=message_to_admin, parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                LOGGER.error(f"Failed to send 'do not renew' notification to admin {admin_id}: {e}")