# FILE: modules/customer/actions/test_account.py (REWRITTEN FOR CONVERSATION)

import logging
import qrcode
import io
import html
import secrets
import string
import re
import datetime
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from modules.general.actions import start
from database.db_manager import (
    load_bot_settings,
    get_user_test_account_count,
    increment_user_test_account_count,
    add_user_to_managed_list,
    save_user_note,
    link_user_to_telegram,
    is_user_admin,cleanup_marzban_user_data
)
from modules.marzban.actions.add_user import create_marzban_user_from_template
# (NEW) Import API to check for existing users
from modules.marzban.actions import api as marzban_api
from shared.translator import _
from shared.log_channel import send_log
from shared.callbacks import end_conversation_and_show_menu
from shared.keyboards import get_connection_guide_keyboard
LOGGER = logging.getLogger(__name__)

# (NEW) Define states for the conversation
ASK_USERNAME = 0


# =================================================================
# [جدید] تابع کمکی برای جاب یک‌بار مصرف حذف اکانت تست
# =================================================================
async def _cleanup_test_account_job(context: ContextTypes.DEFAULT_TYPE):
    """
    این تابع توسط JobQueue در زمان انقضا فراخوانی می‌شود.
    اکانت تست را از مرزبان و دیتابیس محلی حذف کرده و به کاربر اطلاع می‌دهد.
    """
    job = context.job
    marzban_username = job.data['marzban_username']
    chat_id = job.data['chat_id']
    
    LOGGER.info(f"Job triggered: Cleaning up expired test account '{marzban_username}' for user {chat_id}.")
    
    try:
        # مرحله ۱: حذف کاربر از پنل مرزبان
        success, message = await marzban_api.delete_user_api(marzban_username)
        if success:
            LOGGER.info(f"Successfully deleted test account '{marzban_username}' from Marzban panel.")
            # مرحله ۲: پاکسازی اطلاعات کاربر از دیتابیس ربات
            await cleanup_marzban_user_data(marzban_username)
            
            # مرحله ۳: ارسال پیام به کاربر
            keyboard = get_connection_guide_keyboard(is_for_test_account_expired=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text=_("customer.test_account.account_expired_notification"),
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            LOGGER.error(f"Failed to delete expired test account '{marzban_username}' from Marzban. API Error: {message}")
            # حتی اگر حذف از پنل ناموفق بود، به کاربر اطلاع می‌دهیم
            await context.bot.send_message(
                chat_id=chat_id,
                text=_("customer.test_account.account_expired_notification_api_fail"),
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        LOGGER.error(f"Critical error in _cleanup_test_account_job for user {marzban_username}: {e}", exc_info=True)


# ... (بقیه کد فایل از اینجا شروع می‌شود) ...
# async def handle_test_account_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
# ...

async def handle_test_account_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    (REWRITTEN) Starts the test account conversation.
    Checks limits and asks for the desired username.
    (MODIFIED to handle both Message and CallbackQuery)
    """
    user = update.effective_user
    chat_id = update.effective_chat.id
    query = update.callback_query

    async def reply(text):
        """Helper to send message regardless of entry point."""
        if query:
            # For callbacks, always send a new message as this starts a conversation
            await context.bot.send_message(chat_id, text)
        else:
            await update.message.reply_text(text)

    bot_settings = await load_bot_settings()
    is_enabled = bot_settings.get('is_test_account_enabled', False)
    
    if not is_enabled:
        await reply(_("customer.test_account.not_available"))
        return ConversationHandler.END

    if query:
        await query.answer()
        # Clean up the broadcast message
        if query.message:
            await query.message.delete()

    user_is_admin = await is_user_admin(user.id)

    if not user_is_admin:
        limit = bot_settings.get('test_account_limit', 1)
        if not isinstance(limit, int) or limit < 0:
            limit = 1
            LOGGER.warning("Invalid 'test_account_limit' in settings. Defaulting to 1.")
            
        received_count = await get_user_test_account_count(user.id)
        
        if received_count >= limit:
            await reply(_("customer.test_account.limit_reached", limit=limit))
            return ConversationHandler.END
    
    await reply(_("customer.test_account.prompt_for_username"))
    return ASK_USERNAME

# FILE: modules/customer/actions/test_account.py

# (این تابع را به طور کامل جایگزین کنید)
async def get_username_and_create_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    (MODIFIED) Receives the username, validates it, creates the test account,
    schedules a one-shot cleanup job, and sends the result.
    """
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

    bot_settings = await load_bot_settings()
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
    
    # [مهم و جدید] زمان انقضای کاربر را از API بگیرید
    expire_timestamp = new_user_data.get('expire')

    # Perform all database operations
    await increment_user_test_account_count(user.id)
    await link_user_to_telegram(marzban_username, user.id)
    await add_user_to_managed_list(marzban_username)
    await save_user_note(marzban_username, {
        'subscription_duration': round(days_from_hours, 2),
        'subscription_data_limit_gb': gb,
        'subscription_price': 0,
        'is_test_account': True
    })
    
    # =================================================================
    # [جدید] زمان‌بندی جاب یک‌بار مصرف برای حذف اکانت در زمان انقضا
    # =================================================================
    if expire_timestamp and context.job_queue:
        expire_datetime = datetime.datetime.fromtimestamp(expire_timestamp)
        job_data = {
            'marzban_username': marzban_username,
            'chat_id': update.effective_chat.id
        }
        context.job_queue.run_once(
            _cleanup_test_account_job,
            when=expire_datetime,
            data=job_data,
            name=f"cleanup_test_{marzban_username}"
        )
        LOGGER.info(f"Scheduled one-shot cleanup job for test account '{marzban_username}' at {expire_datetime}")
    else:
        LOGGER.warning(f"Could not schedule cleanup job for '{marzban_username}'. Expire timestamp or job_queue not found.")

    caption_text = _("customer.test_account.success_v2", hours=hours, gb=gb)
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