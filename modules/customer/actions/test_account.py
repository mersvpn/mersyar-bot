# FILE: modules/customer/actions/test_account.py

import logging
import random
import string
import qrcode
import io
import html
import time
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db_manager import (
    load_bot_settings,
    get_user_test_account_count,
    increment_user_test_account_count,
    link_user_to_telegram,
    load_template_config_db,
    is_user_admin
)
from modules.marzban.actions.api import create_user_api
from shared.translator import _
from shared.log_channel import send_log

LOGGER = logging.getLogger(__name__)

async def handle_test_account_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the customer's request for a test account.
    The limit on the number of test accounts is now bypassed for admins.
    """
    user_id = update.effective_user.id
    user_info = update.effective_user
    
    bot_settings = await load_bot_settings()
    is_enabled = bot_settings.get('is_test_account_enabled', False)
    
    if not is_enabled:
        await update.message.reply_text(_("customer.test_account.not_available"))
        return

    user_is_admin = await is_user_admin(user_id)

    if not user_is_admin:
        admin_limit = bot_settings.get('test_account_limit', 1)
        user_received_count = await get_user_test_account_count(user_id)
        
        if user_received_count >= admin_limit:
            await update.message.reply_text(_("customer.test_account.limit_reached", limit=admin_limit))
            return

    processing_message = await update.message.reply_text(_("customer.test_account.processing"))

    hours = bot_settings.get('test_account_hours')
    gb = bot_settings.get('test_account_gb')

    if not hours or not gb:
        LOGGER.error("Admin error: Test account is enabled but hours or GB are not set.")
        await processing_message.edit_text(_("customer.test_account.admin_error"))
        return

    template_config = await load_template_config_db()
    if not template_config.get("proxies"):
        LOGGER.error("Admin error: Template user is not configured.")
        await processing_message.edit_text(_("customer.test_account.admin_error"))
        return
        
    user_received_count_for_username = await get_user_test_account_count(user_id)
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    username = f"test_{user_id}_{user_received_count_for_username + 1}_{random_suffix}"
    
    data_limit_bytes = int(float(gb) * 1024 * 1024 * 1024)
    expire_duration_seconds = int(hours * 3600)
    expire_timestamp = int(time.time()) + expire_duration_seconds
    
    user_data = {
        "proxies": template_config.get("proxies", {}),
        "inbounds": template_config.get("inbounds", {}),
        "expire": expire_timestamp,
        "data_limit": data_limit_bytes,
        "username": username,
    }

    success, api_result = await create_user_api(user_data)

    if not success:
        error_message = api_result if isinstance(api_result, str) else "Unknown API error"
        LOGGER.error(f"Failed to create test account for user {user_id}. API Error: {error_message}")
        await processing_message.edit_text(_("customer.test_account.api_failed"))
        await send_log(
            bot=context.bot,
            text=_("log.test_account.api_failed_admin", user_id=user_id, error=error_message)
        )
        return

    sub_link = api_result.get("subscription_url", "N/A")
    all_links = api_result.get("links", [])
    
    await increment_user_test_account_count(user_id)
    await link_user_to_telegram(username, user_id)
    
    caption_text = _("customer.test_account.success_v2", hours=hours, gb=gb)
    caption_text += f"\n\n<code>{html.escape(sub_link)}</code>"

    qr_code_image = None
    if sub_link != "N/A":
        try:
            qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
            qr.add_data(sub_link)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buffer = io.BytesIO()
            img.save(buffer, 'PNG')
            buffer.seek(0)
            qr_code_image = buffer
        except Exception as e:
            LOGGER.error(f"Failed to generate QR code: {e}")

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
            parse_mode=ParseMode.HTML
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

    log_message = _("log.test_account.success_admin",
                    name=user_info.full_name,
                    username=f"@{user_info.username}" if user_info.username else "N/A",
                    user_id=user_id,
                    test_username=username,
                    is_admin_flag=" (Admin)" if user_is_admin else "")
    await send_log(bot=context.bot, text=log_message)