# FILE: modules/customer/actions/test_account.py (FINAL, FULLY CORRECTED VERSION)

import logging
import qrcode
import io
import html
import re
import datetime
import pytz  # (✨ NEW) Import pytz for timezone handling
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from database.crud import bot_setting as crud_bot_setting
from database.crud import user as crud_user
from database.crud import user_note as crud_user_note
from database.crud import marzban_link as crud_marzban_link
from database.crud import bot_managed_user as crud_bot_managed_user
from modules.marzban.actions.add_user import create_marzban_user_from_template
from modules.marzban.actions import api as marzban_api
from shared.translator import _
from shared.log_channel import send_log
from shared.callbacks import end_conversation_and_show_menu
from shared.keyboards import get_connection_guide_keyboard
from shared.auth import is_user_admin

LOGGER = logging.getLogger(__name__)

ASK_USERNAME = 0


async def _cleanup_test_account_job(context: ContextTypes.DEFAULT_TYPE):
    """
    This job runs exactly when a test account expires.
    It notifies the user and then deletes the account.
    """
    job = context.job
    marzban_username = job.data['marzban_username']
    chat_id = job.data['chat_id']
    
    LOGGER.info(f"Job triggered: Notifying user {chat_id} about expired test account '{marzban_username}'.")
    
    try:
        # Step 1: Notify the user that their test is over and encourage purchase.
        # We use a special keyboard for this notification.
        keyboard = get_connection_guide_keyboard(is_for_test_account_expired=True)
        await context.bot.send_message(
            chat_id=chat_id,
            text=_("customer.test_account.account_expired_notification", username=f"<code>{marzban_username}</code>"),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        LOGGER.info(f"Successfully sent expiration notice to user {chat_id}.")

        # Step 2: Now, attempt to delete the user from Marzban.
        success, message = await marzban_api.delete_user_api(marzban_username)
        
        # If deletion was successful OR the user was already gone (404), we clean up the database.
        if success or ("User not found" in message):
            if not success:
                LOGGER.warning(f"Test account '{marzban_username}' was already deleted from Marzban panel. Proceeding with DB cleanup.")
            else:
                LOGGER.info(f"Successfully deleted test account '{marzban_username}' from Marzban panel.")
            
            # Step 3: Clean up all associated data from our bot's database.
            await crud_marzban_link.delete_marzban_link(marzban_username)
            await crud_user_note.delete_user_note(marzban_username)
            await crud_bot_managed_user.remove_from_managed_list(marzban_username)
            LOGGER.info(f"Database cleanup for '{marzban_username}' completed.")
        else:
            # This block only runs for REAL API errors (e.g., connection issues).
            LOGGER.error(f"Failed to delete expired test account '{marzban_username}' from Marzban. API Error: {message}")
            # We still send a message, but it's a slightly different one indicating a potential issue.
            await context.bot.send_message(
                chat_id=chat_id,
                text=_("customer.test_account.account_expired_notification_api_fail"),
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        LOGGER.error(f"Critical error in _cleanup_test_account_job for user {marzban_username}: {e}", exc_info=True)


async def handle_test_account_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    chat_id = update.effective_chat.id
    query = update.callback_query

    async def reply(text):
        if query:
            # Make sure to answer the query to remove the loading icon
            await query.answer()
            await context.bot.send_message(chat_id, text)
        else:
            await update.message.reply_text(text)

    bot_settings = await crud_bot_setting.load_bot_settings()
    is_enabled = bot_settings.get('is_test_account_enabled', False)
    
    if not is_enabled:
        await reply(_("customer.test_account.not_available"))
        return ConversationHandler.END

    if query and query.message:
        # If it's a callback query, we might want to delete the message it came from
        await query.message.delete()

    user_is_admin = await is_user_admin(user.id)

    if not user_is_admin:
        limit = bot_settings.get('test_account_limit', 1)
        if not isinstance(limit, int) or limit < 0:
            limit = 1
            LOGGER.warning("Invalid 'test_account_limit' in settings. Defaulting to 1.")
            
        received_count = await crud_user.get_user_test_account_count(user.id)
        
        if received_count >= limit:
            await reply(_("customer.test_account.limit_reached", limit=limit))
            return ConversationHandler.END
    
    await reply(_("customer.test_account.prompt_for_username"))
    return ASK_USERNAME


async def get_username_and_create_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    base_username = update.message.text.strip()
    
    if not base_username or ' ' in base_username or not re.match(r"^[a-zA-Z0-9_]+$", base_username):
        await update.message.reply_text(_("customer.test_account.invalid_username"))
        return ASK_USERNAME

    final_username = f"{base_username}test"

    existing_user = await marzban_api.get_user_data(final_username)
    if existing_user and "error" not in existing_user:
        error_text = _("customer.test_account.username_taken", final_username=final_username)
        await update.message.reply_text(error_text, parse_mode=ParseMode.MARKDOWN)
        return ASK_USERNAME

    processing_message = await update.message.reply_text(_("customer.test_account.processing"))

    bot_settings = await crud_bot_setting.load_bot_settings()
    hours = bot_settings.get('test_account_hours')
    gb = bot_settings.get('test_account_gb')
    days_from_hours = (hours / 24) if hours else 0

    if not hours or not gb or hours <= 0 or gb <= 0:
        LOGGER.error(f"Admin config error for test account. Hours: {hours}, GB: {gb}")
        await processing_message.edit_text(_("customer.test_account.admin_error"))
        return ConversationHandler.END

    new_user_data = await create_marzban_user_from_template(
        data_limit_gb=gb,
        expire_days=days_from_hours,
        username=final_username
    )

    if not new_user_data:
        LOGGER.error(f"Failed to create test account for user {user.id} with username {final_username}.")
        await processing_message.edit_text(_("customer.test_account.api_failed"))
        await send_log(
            bot=context.bot,
            text=f"🔴 *API Error for Test Account*\n\nUser: {user.id}\nUsername: `{final_username}`\nCould not create user.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    marzban_username = new_user_data['username']
    sub_link = new_user_data.get("subscription_url", "N/A")
    all_links = new_user_data.get("links", [])
    expire_timestamp = new_user_data.get('expire')

    await crud_user.increment_user_test_account_count(user.id)
    await crud_marzban_link.create_or_update_link(marzban_username, user.id)
    await crud_bot_managed_user.add_to_managed_list(marzban_username)
    
    await crud_user_note.create_or_update_user_note(
        marzban_username=marzban_username,
        duration=round(days_from_hours, 2),
        data_limit_gb=gb,
        price=0,
        is_test_account=True
    )
    
    # --- (✨ FIX START) TIMEZONE CORRECTION ---
    if expire_timestamp and context.job_queue:
        try:
            # 1. Assume the timestamp from Marzban is based on Tehran time.
            # Create a "naive" datetime object from it first.
            naive_expire_dt = datetime.datetime.fromtimestamp(expire_timestamp)
            
            # 2. Get the Tehran timezone object.
            tehran_tz = pytz.timezone("Asia/Tehran")
            
            # 3. Localize the naive datetime, making it "aware" of the Tehran timezone.
            tehran_aware_dt = tehran_tz.localize(naive_expire_dt)
            
            # 4. Convert this Tehran-aware time to UTC. APScheduler works best with UTC.
            utc_expire_dt = tehran_aware_dt.astimezone(pytz.utc)
            
            job_data = {
                'marzban_username': marzban_username,
                'chat_id': update.effective_chat.id
            }
            
            # 5. Schedule the job using the correctly converted UTC datetime.
            context.job_queue.run_once(
                _cleanup_test_account_job,
                when=utc_expire_dt,
                data=job_data,
                name=f"cleanup_test_{marzban_username}"
            )
            LOGGER.info(f"Scheduled one-shot cleanup job for test account '{marzban_username}' at {tehran_aware_dt} (Tehran) / {utc_expire_dt} (UTC)")

        except (pytz.UnknownTimeZoneError, Exception) as e:
            LOGGER.error(f"CRITICAL: Failed to schedule cleanup job for '{marzban_username}' due to a timezone error: {e}", exc_info=True)
            # As a fallback, we log this critical error. The hourly cleanup job will eventually get this user.
    elif not context.job_queue:
        LOGGER.warning(f"JobQueue not available. Cannot schedule cleanup for '{marzban_username}'.")
    # --- (✨ FIX END) ---

    caption_text = _("customer.test_account.success_v2", hours=hours, gb=gb, username=f"<code>{html.escape(marzban_username)}</code>")
    caption_text += f"\n\n<code>{html.escape(sub_link)}</code>"
    
    reply_markup = get_connection_guide_keyboard()
    
    qr_code_image = None
    if "N/A" not in sub_link:
        try:
            img = qrcode.make(sub_link)
            buffer = io.BytesIO()
            img.save(buffer, 'PNG')
            buffer.seek(0)
            qr_code_image = buffer
        except Exception as e:
            LOGGER.error(f"Failed to generate QR code for test account: {e}")

    await processing_message.delete()
    
    if qr_code_image:
        await update.message.reply_photo(
            photo=qr_code_image, 
            caption=caption_text, 
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            text=caption_text, 
            parse_mode=ParseMode.HTML, 
            disable_web_page_preview=True,
            reply_markup=reply_markup
        )

    if all_links:
        links_message_text = _("customer.test_account.individual_links_title") + "\n\n"
        links_str = "\n".join([f"<code>{html.escape(link)}</code>" for link in all_links])
        links_message_text += links_str
        await update.message.reply_text(text=links_message_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    user_is_admin = await is_user_admin(user.id)
    admin_flag = " (Admin)" if user_is_admin else ""
    log_message = (
        f"🧪 *Test Account Created*{admin_flag}\n\n"
        f"👤 **User:** {user.mention_html()}\n"
        f"🆔 **ID:** `{user.id}`\n"
        f"🤖 **Marzban User:** `{marzban_username}`"
    )
    await send_log(bot=context.bot, text=log_message, parse_mode=ParseMode.HTML)

    from shared.keyboards import get_customer_main_menu_keyboard
    
    keyboard = await get_customer_main_menu_keyboard(user_id=user.id)
    
    await update.message.reply_text(
        _("general.returned_to_main_menu"), 
        reply_markup=keyboard
    )
    
    return ConversationHandler.END