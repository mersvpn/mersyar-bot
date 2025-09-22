# FILE: modules/marzban/actions/add_user.py (FULLY UPDATED TO NEW TRANSLATION STANDARD)

import datetime
import qrcode
import io
import logging
import copy
import secrets
import string
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from .constants import (
    ADD_USER_USERNAME, ADD_USER_DATALIMIT, ADD_USER_EXPIRE, ADD_USER_CONFIRM,
    GB_IN_BYTES
)
from database.db_manager import (
    load_template_config_db, link_user_to_telegram, save_user_note,
    add_user_to_managed_list
)
from shared.keyboards import get_user_management_keyboard
from modules.general.actions import end_conversation_and_show_menu
from .api import create_user_api, get_user_data
from .data_manager import normalize_username
from shared.log_channel import send_log

LOGGER = logging.getLogger(__name__)

def generate_random_username(length=8):
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(length))

async def create_marzban_user_from_template(
    data_limit_gb: int, expire_days: int, username: Optional[str] = None, max_ips: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    template_config = await load_template_config_db()
    if not template_config.get("template_username"):
        LOGGER.error("[Core Create User] Template user is not configured in the database.")
        return None

    base_username = username or generate_random_username()
    base_username = normalize_username(base_username)

    data_limit = data_limit_gb * GB_IN_BYTES if data_limit_gb > 0 else 0
    expire_timestamp = (datetime.datetime.now() + datetime.timedelta(days=expire_days)).timestamp() if expire_days > 0 else 0
    expire = int(expire_timestamp)
    
    proxies_from_template = copy.deepcopy(template_config.get('proxies', {}))
    for proto in ['vless', 'vmess']:
        if proto in proxies_from_template and 'id' in proxies_from_template[proto]:
            del proxies_from_template[proto]['id']
    
    payload = {
        "inbounds": template_config.get('inbounds', {}), "expire": expire,
        "data_limit": data_limit, "proxies": proxies_from_template, "status": "active"
    }

    if max_ips is not None and max_ips > 0:
        payload["on_hold_max_ips"] = max_ips
        LOGGER.info(f"[Core Create User] Setting max_online_ips to {max_ips} for user {base_username}.")

    current_username = base_username
    for attempt in range(4):
        payload["username"] = current_username
        success, result = await create_user_api(payload)
        
        if success:
            LOGGER.info(f"[Core Create User] Successfully created user '{current_username}' via API.")
            return result
        
        if isinstance(result, str) and "already exists" in result:
            LOGGER.warning(f"[Core Create User] Username '{current_username}' already exists. Generating a new one.")
            current_username = f"{base_username}_{secrets.choice(string.digits)}{secrets.choice(string.digits)}"
            continue
        else:
            LOGGER.error(f"[Core Create User] Failed to create user '{current_username}'. API response: {result}")
            return None

    LOGGER.error(f"[Core Create User] Failed to create user after 4 attempts. Last tried: '{current_username}'.")
    return None

async def add_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    context.user_data.pop('customer_user_id', None)
    template_config = await load_template_config_db()
    if not template_config.get("template_username"):
        # --- FIX: Added 'marzban.' namespace ---
        await update.message.reply_text(
            _("marzban.marzban_add_user.template_not_set"),
            parse_mode=ParseMode.MARKDOWN, reply_markup=get_user_management_keyboard()
        )
        return ConversationHandler.END
    # --- FIX: Added 'marzban.' namespace ---
    await update.message.reply_text(
        _("marzban.marzban_add_user.step1_ask_username"),
        reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['new_user'] = {}
    return ADD_USER_USERNAME

async def add_user_for_customer_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query
    await query.answer()
    customer_user_id = int(query.data.split('_')[-1])
    context.user_data['customer_user_id'] = customer_user_id
    template_config = await load_template_config_db()
    if not template_config.get("template_username"):
        # --- FIX: Added 'marzban.' namespace ---
        await query.message.reply_text(_("marzban.marzban_add_user.template_not_set"), parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END
    # --- FIX: Added 'marzban.' namespace ---
    await query.edit_message_text(_("marzban.marzban_add_user.request_approved_creating_for", customer_id=f"`{customer_user_id}`"), parse_mode=ParseMode.MARKDOWN)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        # --- FIX: Added 'marzban.' namespace ---
        text=_("marzban.marzban_add_user.step1_ask_username_for_customer"),
        reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.MARKDOWN
    )
    context.user_data['new_user'] = {}
    return ADD_USER_USERNAME

async def add_user_get_username(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    username = normalize_username(update.message.text)
    if not username or ' ' in username:
        # --- FIX: Added 'marzban.' namespace ---
        await update.message.reply_text(_("marzban.marzban_add_user.invalid_username"))
        return ADD_USER_USERNAME

    existing_user = await get_user_data(username)
    if existing_user and "error" not in existing_user:
        # --- FIX: Added 'marzban.' namespace ---
        await update.message.reply_text(_("marzban.marzban_add_user.username_exists", username=username), parse_mode=ParseMode.MARKDOWN)
        return ADD_USER_USERNAME
    
    context.user_data['new_user']['username'] = username
    # --- FIX: Added 'marzban.' namespace ---
    message = _("marzban.marzban_add_user.username_ok", username=f"`{username}`") + _("marzban.marzban_add_user.step2_ask_datalimit")
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
    return ADD_USER_DATALIMIT

async def add_user_get_datalimit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    try:
        data_gb = int(update.message.text)
        if data_gb < 0: raise ValueError
        context.user_data['new_user']['data_limit_gb'] = data_gb
        # --- FIX: Added 'marzban.' namespace ---
        datalimit_str = _("marzban.marzban_display.unlimited") if data_gb == 0 else data_gb
        # --- FIX: Added 'marzban.' namespace ---
        message = _("marzban.marzban_add_user.datalimit_ok", datalimit=f"`{datalimit_str}`") + _("marzban.marzban_add_user.step3_ask_expire")
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        return ADD_USER_EXPIRE
    except (ValueError, TypeError):
        # --- FIX: Added 'marzban.' namespace ---
        await update.message.reply_text(_("marzban.marzban_add_user.invalid_number"))
        return ADD_USER_DATALIMIT

async def add_user_get_expire(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    try:
        expire_days = int(update.message.text)
        if expire_days < 0: raise ValueError
        context.user_data['new_user']['expire_days'] = expire_days
        user_info = context.user_data['new_user']
        username = user_info['username']
        # --- FIX: Added 'marzban.' namespace ---
        data_gb_str = _("marzban.marzban_display.unlimited") if user_info['data_limit_gb'] == 0 else user_info['data_limit_gb']
        expire_days_str = _("marzban.marzban_display.unlimited") if expire_days == 0 else expire_days
        
        # --- FIX: All keys now use the 'marzban.' namespace ---
        summary = _("marzban.marzban_add_user.confirm_prompt_title")
        summary += _("marzban.marzban_add_user.confirm_username", username=f"`{username}`")
        summary += _("marzban.marzban_add_user.confirm_datalimit", datalimit=f"`{data_gb_str}`")
        summary += _("marzban.marzban_add_user.confirm_expire", duration=f"`{expire_days_str}`")
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("marzban.marzban_add_user.button_confirm_create"), callback_data="confirm_add_user")],
            [InlineKeyboardButton(_("marzban.marzban_add_user.button_cancel"), callback_data="cancel_add_user")]
        ])
        await update.message.reply_text(summary, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
        return ADD_USER_CONFIRM
    except (ValueError, TypeError):
        # --- FIX: Added 'marzban.' namespace ---
        await update.message.reply_text(_("marzban.marzban_add_user.invalid_number"))
        return ADD_USER_EXPIRE

async def add_user_create(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    query = update.callback_query
    await query.answer()
    
    admin_user = update.effective_user
    # --- FIX: Added 'marzban.' namespace ---
    await query.edit_message_text(_("marzban.marzban_add_user.creating_user"), parse_mode=ParseMode.MARKDOWN)

    user_info = context.user_data.get('new_user')
    if not user_info:
        # --- FIX: Added 'marzban.' namespace ---
        await query.edit_message_text(_("marzban.marzban_add_user.error_user_info_lost"))
        return ConversationHandler.END

    new_user_data = await create_marzban_user_from_template(
        data_limit_gb=user_info['data_limit_gb'], expire_days=user_info['expire_days'], username=user_info['username']
    )
    
    if new_user_data:
        marzban_username = new_user_data['username']
        normalized_username = normalize_username(marzban_username)

        await add_user_to_managed_list(normalized_username)
        await save_user_note(normalized_username, {
            'subscription_duration': user_info['expire_days'], 
            'subscription_data_limit_gb': user_info['data_limit_gb'],
            'subscription_price': 0
        })
        
        admin_mention = escape_markdown(admin_user.full_name, version=2)
        safe_username = escape_markdown(marzban_username, version=2)
        # --- FIX: Added 'marzban.' namespace ---
        log_message = _("marzban.marzban_add_user.log_new_user_created", 
                        username=safe_username, datalimit=user_info['data_limit_gb'], 
                        duration=user_info['expire_days'], admin_mention=admin_mention)
        await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN_V2)

        customer_id = context.user_data.get('customer_user_id')
        if customer_id:
            await link_user_to_telegram(normalized_username, customer_id)
            subscription_url = new_user_data.get('subscription_url', '')
            if subscription_url:
                # --- FIX: Added 'marzban.' namespace ---
                data_limit_str = f"{user_info['data_limit_gb']} GB" if user_info['data_limit_gb'] > 0 else _("marzban.marzban_display.unlimited")
                expire_days_str = f"{user_info['expire_days']} روز" if user_info['expire_days'] > 0 else _("marzban.marzban_display.unlimited")
                
                # --- FIX: All keys now use the 'marzban.' namespace ---
                customer_message = _("marzban.marzban_add_user.customer_message_title")
                customer_message += _("marzban.marzban_add_user.customer_message_username", username=f"`{marzban_username}`")
                customer_message += _("marzban.marzban_add_user.customer_message_datalimit", datalimit=data_limit_str)
                customer_message += _("marzban.marzban_add_user.customer_message_duration", duration=expire_days_str)
                customer_message += _("marzban.marzban_add_user.customer_message_sub_link", url=subscription_url)
                customer_message += _("marzban.marzban_add_user.customer_message_guide")
                
                qr_image = qrcode.make(subscription_url)
                bio = io.BytesIO()
                bio.name = 'qrcode.png'
                qr_image.save(bio, 'PNG')
                bio.seek(0)
                try:
                    await context.bot.send_photo(chat_id=customer_id, photo=bio, caption=customer_message, parse_mode=ParseMode.MARKDOWN)
                    callback_string = f"fin_send_req:{customer_id}:{marzban_username}"
                    # --- FIX: Added 'marzban.' namespace ---
                    admin_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("marzban.marzban_add_user.button_send_invoice"), callback_data=callback_string)]])
                    await context.bot.send_message(chat_id=admin_user.id, text=_("marzban.marzban_add_user.config_sent_to_customer", customer_id=customer_id), reply_markup=admin_keyboard)
                except Exception as e:
                    LOGGER.warning(f"Failed to send message to customer {customer_id}: {e}")
                    await context.bot.send_message(chat_id=admin_user.id, text=_("marzban.marzban_add_user.error_sending_to_customer", url=subscription_url))
        
        # --- FIX: Added 'marzban.' namespace ---
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("marzban.marzban_add_user.button_view_user_details"), callback_data=f"user_details_{marzban_username}_all_1")]
        ])
        await query.edit_message_text(_("marzban.marzban_add_user.user_created_successfully", username=f"`{marzban_username}`"), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    else:
        # --- FIX: Added 'marzban.' namespace ---
        error_message = _("marzban.marzban_add_user.error_creating_user", error=f"`{new_user_data}`")
        await query.edit_message_text(error_message, parse_mode=ParseMode.MARKDOWN)
    
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
    return await end_conversation_and_show_menu(update, context)