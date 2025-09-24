# FILE: modules/customer/actions/test_account.py (REWRITTEN FOR CONVERSATION)

import logging
import qrcode
import io
import html
import secrets
import string
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
    is_user_admin
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

async def handle_test_account_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    (REWRITTEN) Starts the test account conversation.
    Checks limits and asks for the desired username.
    """
    user = update.effective_user
    
    bot_settings = await load_bot_settings()
    is_enabled = bot_settings.get('is_test_account_enabled', False)
    
    if not is_enabled:
        await update.message.reply_text(_("customer.test_account.not_available"))
        return ConversationHandler.END

    user_is_admin = await is_user_admin(user.id)

    if not user_is_admin:
        limit = bot_settings.get('test_account_limit', 1)
        if not isinstance(limit, int) or limit < 0:
            limit = 1
            LOGGER.warning("Invalid 'test_account_limit' in settings. Defaulting to 1.")
            
        received_count = await get_user_test_account_count(user.id)
        
        if received_count >= limit:
            await update.message.reply_text(_("customer.test_account.limit_reached", limit=limit))
            return ConversationHandler.END
    
    await update.message.reply_text(_("customer.test_account.prompt_for_username"))
    return ASK_USERNAME
async def get_username_and_create_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    (MODIFIED) Receives the username, appends 'test', validates it, creates the test account,
    and sends the result with a connection guide button.
    """
    user = update.effective_user
    base_username = update.message.text.strip()
    final_username = f"{base_username}test"

    if not base_username or ' ' in base_username:
        await update.message.reply_text(_("customer.test_account.invalid_username"))
        return ASK_USERNAME

    existing_user = await marzban_api.get_user_data(final_username)
    if existing_user:
        await update.message.reply_text(_("marzban.marzban_add_user.username_taken") + f"\n(نام کاربری نهایی `{final_username}` قبلاً استفاده شده است.)")
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
    
    caption_text = _("customer.test_account.success_v2", hours=hours, gb=gb)
    caption_text += f"\n\n<code>{html.escape(sub_link)}</code>"
    
    # --- CHANGE START: Create the keyboard ---
    reply_markup = get_connection_guide_keyboard()
    # --- CHANGE END ---
    
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
        # --- CHANGE START: Add reply_markup to the message ---
        await update.message.reply_photo(
            photo=qr_code_image, 
            caption=caption_text, 
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        # --- CHANGE END ---
    else:
        # --- CHANGE START: Add reply_markup to the message ---
        await update.message.reply_text(
            text=caption_text, 
            parse_mode=ParseMode.HTML, 
            disable_web_page_preview=True,
            reply_markup=reply_markup
        )
        # --- CHANGE END ---

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

    
    return ConversationHandler.END