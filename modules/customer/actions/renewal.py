# --- START OF FILE modules/customer/actions/renewal.py ---

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from config import config
from modules.marzban.actions.data_manager import normalize_username
from shared.translator import _
# --- MODIFIED IMPORTS ---
from database.crud import user_note as crud_user_note
from database.crud import non_renewal_user as crud_non_renewal_user
from modules.payment.actions.renewal import send_renewal_invoice_to_user

LOGGER = logging.getLogger(__name__)


async def handle_renewal_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handles a renewal request from a customer.
    This function now automatically generates and sends a renewal invoice to the customer.
    """
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    marzban_username = query.data.split('_')[-1]
    
    # Get subscription details from the database using the new CRUD function
    note_data = await crud_user_note.get_user_note(marzban_username)
    
    # Check if a note exists first, then check its attributes
    if not note_data:
        price, duration, data_limit_gb = None, None, 0
    else:
        price = note_data.subscription_price
        duration = note_data.subscription_duration
        data_limit_gb = note_data.subscription_data_limit_gb or 0 # Default to 0 if None

    # Check if subscription details are valid
    if price is None or duration is None or price <= 0 or duration <= 0:
        LOGGER.warning(f"User {user_id} requested renewal for '{marzban_username}', but no valid subscription info was found.")
        await query.edit_message_text(
            text=_("renewal.error_no_subscription_info"),
            reply_markup=None
        )
        # We also inform admins so they can fix the user's note data
        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=_("renewal.admin_alert_missing_info", username=f"`{marzban_username}`"),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                LOGGER.error(f"Failed to send missing info alert to admin {admin_id}: {e}")
        return ConversationHandler.END

    # If details are valid, create and send the invoice using the central function
    await query.edit_message_text(text=_("renewal.generating_invoice"), reply_markup=None)
    
    await send_renewal_invoice_to_user(
        context=context,
        user_telegram_id=user_id,
        username=marzban_username,
        renewal_days=duration,
        price=price,
        data_limit_gb=data_limit_gb
    )

    return ConversationHandler.END


async def handle_do_not_renew(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the user's choice to opt-out of renewal reminders."""
    query = update.callback_query
    await query.answer()

    marzban_username = query.data.split('_')[-1]
    normalized_user = normalize_username(marzban_username)
    user = update.effective_user

    LOGGER.info(f"User {user.id} ({normalized_user}) opted out of renewal reminders.")

    # Use the new CRUD function to add to the non-renewal list
    await crud_non_renewal_user.add_to_non_renewal_list(normalized_user)

    await query.edit_message_text(_("renewal.do_not_renew_success"))

    if config.AUTHORIZED_USER_IDS:
        safe_full_name = escape_markdown(user.full_name)
        user_info = f"کاربر {safe_full_name}"
        if user.username:
            user_info += f" (@{user.username})"
        
        safe_normalized_user = escape_markdown(normalized_user)
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

# --- END OF FILE modules/customer/actions/renewal.py ---