# FILE: modules/customer/actions/test_account.py (FINAL VERSION, COMPATIBLE WITH NEW TRANSLATOR)

import logging
import qrcode
import io
import html
import secrets
import string
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

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
from shared.translator import _
from shared.log_channel import send_log

LOGGER = logging.getLogger(__name__)

def generate_test_username(user_id: int) -> str:
    """Generates a unique and identifiable username for a test account."""
    random_part = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4))
    return f"test_{user_id}_{random_part}"

async def handle_test_account_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the customer's request for a test account.
    This version uses correct, namespaced translator keys.
    """
    user = update.effective_user
    
    bot_settings = await load_bot_settings()
    is_enabled = bot_settings.get('is_test_account_enabled', False)
    
    if not is_enabled:
        await update.message.reply_text(_("customer.test_account.not_available"))
        return

    user_is_admin = await is_user_admin(user.id)

    if not user_is_admin:
        limit = bot_settings.get('test_account_limit', 1)
        if not isinstance(limit, int) or limit < 0:
            limit = 1
            LOGGER.warning("Invalid 'test_account_limit' in settings. Defaulting to 1.")
            
        received_count = await get_user_test_account_count(user.id)
        
        if received_count >= limit:
            await update.message.reply_text(_("customer.test_account.limit_reached", limit=limit))
            return

    processing_message = await update.message.reply_text(_("customer.test_account.processing"))

    hours = bot_settings.get('test_account_hours')
    gb = bot_settings.get('test_account_gb')
    days_from_hours = (hours / 24) if hours else 0

    if not hours or not gb or hours <= 0 or gb <= 0:
        LOGGER.error(f"Admin config error for test account. Enabled: {is_enabled}, Hours: {hours}, GB: {gb}")
        await processing_message.edit_text(_("customer.test_account.admin_error"))
        return

    test_username = generate_test_username(user.id)
    
    new_user_data = await create_marzban_user_from_template(
        data_limit_gb=gb,
        expire_days=days_from_hours,
        username=test_username
    )

    if not new_user_data:
        LOGGER.error(f"Failed to create test account for user {user.id} via create_marzban_user_from_template.")
        await processing_message.edit_text(_("customer.test_account.api_failed"))
        await send_log(
            bot=context.bot,
            text=f"🔴 *API Error for Test Account*\n\nUser: {user.id}\nCould not create user in Marzban panel.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    marzban_username = new_user_data['username']
    sub_link = new_user_data.get("subscription_url", "N/A")
    all_links = new_user_data.get("links", [])

    # --- Post-creation database operations ---
    await increment_user_test_account_count(user.id)
    await link_user_to_telegram(marzban_username, user.id)
    await add_user_to_managed_list(marzban_username)
    await save_user_note(marzban_username, {
        'subscription_duration': round(days_from_hours, 2),
        'subscription_data_limit_gb': gb,
        'subscription_price': 0
    })
    
    caption_text = _("customer.test_account.success_v2", hours=hours, gb=gb)
    caption_text += f"\n\n<code>{html.escape(sub_link)}</code>"
    
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
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            text=caption_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

    if all_links:
        links_message_text = _("customer.test_account.individual_links_title") + "\n\n"
        links_str = "\n".join([f"<code>{html.escape(link)}</code>" for link in all_links])
        links_message_text += links_str
        
        await update.message.reply_text(
            text=links_message_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

    admin_flag = " (Admin)" if user_is_admin else ""
    log_message = (
        f"🧪 *Test Account Created*{admin_flag}\n\n"
        f"👤 **User:** {user.mention_html()}\n"
        f"🆔 **ID:** `{user.id}`\n"
        f"🤖 **Marzban User:** `{marzban_username}`"
    )
    await send_log(bot=context.bot, text=log_message, parse_mode=ParseMode.HTML)