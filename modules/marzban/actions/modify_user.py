# FILE: modules/marzban/actions/modify_user.py (REVISED FOR I18N and BEST PRACTICES)

import datetime
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from shared.log_channel import send_log
from shared.keyboards import get_back_to_main_menu_keyboard

from .display import show_user_details_panel
from .constants import GB_IN_BYTES, DEFAULT_RENEW_DAYS
from .data_manager import normalize_username
from .api import get_user_data, modify_user_api, delete_user_api, reset_user_traffic_api

LOGGER = logging.getLogger(__name__)

ADD_DAYS_PROMPT, ADD_DATA_PROMPT = range(2)

async def _start_modification_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE, prompt_text: str, prefix: str) -> None:
    query = update.callback_query
    username = query.data.removeprefix(prefix)
    
    context.user_data['modify_user_info'] = {
        'username': username, 'chat_id': query.message.chat_id,
        'message_id': query.message.message_id,
        'list_type': context.user_data.get('current_list_type', 'all'),
        'page_number': context.user_data.get('current_page', 1)
    }
    await query.answer()
    await query.message.delete()
    await context.bot.send_message(
        chat_id=query.message.chat_id, text=prompt_text,
        reply_markup=get_back_to_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN
    )

async def prompt_for_add_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    username = update.callback_query.data.removeprefix('add_days_')
    text = _("marzban_modify_user.prompt_add_days", username=f"`{username}`")
    await _start_modification_conversation(update, context, text, 'add_days_')
    return ADD_DAYS_PROMPT

async def prompt_for_add_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    username = update.callback_query.data.removeprefix('add_data_')
    text = _("marzban_modify_user.prompt_add_data", username=f"`{username}`")
    await _start_modification_conversation(update, context, text, 'add_data_')
    return ADD_DATA_PROMPT

async def do_add_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    modify_info = context.user_data.get('modify_user_info')
    if not modify_info:
        await update.message.reply_text(_("marzban_modify_user.conversation_expired"))
        return ConversationHandler.END

    try:
        days_to_add = int(update.message.text)
        if days_to_add <= 0:
            await update.message.reply_text(_("marzban_modify_user.invalid_positive_number"))
            return ADD_DAYS_PROMPT
    except (ValueError, TypeError):
        await update.message.reply_text(_("marzban_modify_user.invalid_number_input"))
        return ADD_DAYS_PROMPT

    await update.message.delete()
    
    username = modify_info['username']
    user_data = await get_user_data(username)
    if not user_data:
        await context.bot.send_message(chat_id=modify_info['chat_id'], text=_("marzban_display.user_not_found"))
        return ConversationHandler.END

    current_expire_ts = user_data.get('expire') or 0
    start_date = datetime.datetime.fromtimestamp(max(current_expire_ts, datetime.datetime.now().timestamp()))
    new_expire_date = start_date + datetime.timedelta(days=days_to_add)
    
    success, message = await modify_user_api(username, {"expire": int(new_expire_date.timestamp())})
    
    success_msg = _("marzban_modify_user.success_add_days", days=days_to_add) if success else _("marzban_modify_user.error_add_days", error=message)
    await show_user_details_panel(context=context, **modify_info, success_message=success_msg)
    
    context.user_data.pop('modify_user_info', None)
    return ConversationHandler.END

async def do_add_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    modify_info = context.user_data.get('modify_user_info')
    if not modify_info:
        await update.message.reply_text(_("marzban_modify_user.conversation_expired"))
        return ConversationHandler.END

    try:
        gb_to_add = int(update.message.text)
        if gb_to_add <= 0:
            await update.message.reply_text(_("marzban_modify_user.invalid_positive_number"))
            return ADD_DATA_PROMPT
    except (ValueError, TypeError):
        await update.message.reply_text(_("marzban_modify_user.invalid_number_input"))
        return ADD_DATA_PROMPT

    await update.message.delete()
    
    username = modify_info['username']
    user_data = await get_user_data(username)
    if not user_data:
        await context.bot.send_message(chat_id=modify_info['chat_id'], text=_("marzban_display.user_not_found"))
        return ConversationHandler.END

    new_data_limit = user_data.get('data_limit', 0) + (gb_to_add * GB_IN_BYTES)
    
    success, message = await modify_user_api(username, {"data_limit": new_data_limit})
    success_msg = _("marzban_modify_user.success_add_data", gb=gb_to_add) if success else _("marzban_modify_user.error_add_data", error=message)
    await show_user_details_panel(context=context, **modify_info, success_message=success_msg)
    context.user_data.pop('modify_user_info', None)
    return ConversationHandler.END

async def reset_user_traffic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    query = update.callback_query
    username = query.data.removeprefix('reset_traffic_')
    await query.answer(_("marzban_modify_user.resetting_traffic", username=username))
    
    success, message = await reset_user_traffic_api(username)
    success_msg = _("marzban_modify_user.traffic_reset_success") if success else _("marzban_modify_user.traffic_reset_error", error=message)

    await show_user_details_panel(
        context=context, chat_id=query.message.chat_id, message_id=query.message.message_id,
        username=username, list_type=context.user_data.get('current_list_type', 'all'),
        page_number=context.user_data.get('current_page', 1), success_message=success_msg
    )

async def confirm_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    query = update.callback_query
    username = query.data.removeprefix('delete_')
    list_type = context.user_data.get('current_list_type', 'all')
    page_number = context.user_data.get('current_page', 1)
    await query.answer()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("marzban_modify_user.button_confirm_delete"), callback_data=f"do_delete_{username}")],
        [InlineKeyboardButton(_("marzban_modify_user.button_cancel_delete"), callback_data=f"user_details_{username}_{list_type}_{page_number}")]
    ])
    await query.edit_message_text(_("marzban_modify_user.delete_confirm_prompt", username=f"`{username}`"), reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def do_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    from database.db_manager import cleanup_marzban_user_data, get_telegram_id_from_marzban_username
    query = update.callback_query
    admin_user = update.effective_user
    username = query.data.removeprefix('do_delete_')
    await query.answer()
    
    is_customer_request = "درخواست حذف سرویس" in query.message.text
    await query.edit_message_text(_("marzban_modify_user.deleting_user", username=f"`{username}`"), parse_mode=ParseMode.MARKDOWN)
    customer_id = await get_telegram_id_from_marzban_username(normalize_username(username))

    success, message = await delete_user_api(username)
    if success:
        await cleanup_marzban_user_data(username)
        admin_mention = escape_markdown(admin_user.full_name, version=2)
        safe_username = escape_markdown(username, version=2)
        
        log_title = _("marzban_modify_user.log_delete_by_customer") if is_customer_request else _("marzban_modify_user.log_delete_by_admin")
        log_message = f"{log_title}\n\n▫️ **نام کاربری:** `{safe_username}`\n"
        log_message += _("marzban_modify_user.log_deleted_by", admin_mention=admin_mention)
        await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN_V2)
        
        await query.edit_message_text(_("marzban_modify_user.delete_successful", username=f"`{username}`"), parse_mode=ParseMode.MARKDOWN)

        if customer_id:
             try:
                await context.bot.send_message(chat_id=customer_id, text=_("marzban_modify_user.notify_customer_delete_success", username=f"`{username}`"))
             except Exception as e:
                LOGGER.warning(f"Config deleted, but failed to notify customer {customer_id}: {e}")
    else:
        await query.edit_message_text(f"❌ {message}", parse_mode=ParseMode.MARKDOWN)

async def renew_user_smart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import _
    from database.db_manager import get_user_note
    from database.db_manager import get_user_note, get_telegram_id_from_marzban_username

    query = update.callback_query
    username = query.data.removeprefix('renew_')
    admin_user = update.effective_user
    
    # Provide immediate feedback to the admin
    await query.answer(_("marzban_modify_user.renewing_user", username=username))
    await query.edit_message_text(
        _("marzban_modify_user.renew_in_progress", username=f"`{username}`"), 
        parse_mode=ParseMode.MARKDOWN
    )

    # --- Step 1: Get User and Subscription Data ---
    user_data = await get_user_data(username)
    if not user_data:
        await query.edit_message_text(_("marzban_display.user_not_found"))
        return

    note_data = await get_user_note(normalize_username(username))
    
    # Use subscription data if available, otherwise use defaults
    renewal_duration_days = (note_data or {}).get('subscription_duration') or DEFAULT_RENEW_DAYS
    data_limit_gb = (note_data or {}).get('subscription_data_limit_gb', (user_data.get('data_limit') or 0) / GB_IN_BYTES)
    
    # --- Step 2: Perform Renewal in Marzban Panel ---
    # 2a. Reset Traffic
    success_reset, message_reset = await reset_user_traffic_api(username)
    if not success_reset:
        await query.edit_message_text(_("marzban_modify_user.renew_error_reset_traffic", error=f"`{message_reset}`"), parse_mode=ParseMode.MARKDOWN)
        return
        
    # 2b. Modify User (Extend expiry, set data limit)
    start_date = datetime.datetime.fromtimestamp(max(user_data.get('expire') or 0, datetime.datetime.now().timestamp()))
    new_expire_date = start_date + datetime.timedelta(days=renewal_duration_days)
    payload_to_modify = {
        "expire": int(new_expire_date.timestamp()), 
        "data_limit": int(data_limit_gb * GB_IN_BYTES), 
        "status": "active"
    }
    
    success_modify, message_modify = await modify_user_api(username, payload_to_modify)
    if not success_modify:
        await query.edit_message_text(_("marzban_modify_user.renew_error_modify", error=f"`{message_modify}`"), parse_mode=ParseMode.MARKDOWN)
        return
        
    # --- Step 3: Log the successful renewal ---
    admin_mention = escape_markdown(admin_user.full_name, version=2)
    safe_username = escape_markdown(username, version=2)
    log_message = _("marzban_modify_user.log_renew_title")
    log_message += _("marzban_modify_user.log_renew_username", username=safe_username)
    log_message += _("marzban_modify_user.log_renew_data", gb=int(data_limit_gb))
    log_message += _("marzban_modify_user.log_renew_duration", days=renewal_duration_days)
    log_message += _("marzban_modify_user.log_deleted_by", admin_mention=admin_mention)
    await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN_V2)

    # --- Step 4: Show Final Success Message to Admin ---
    # This will refresh the user details panel with the new info
    # --- Step 4: Notify the customer (if linked) ---
    customer_id = await get_telegram_id_from_marzban_username(normalize_username(username))
    customer_notified = False
    if customer_id:
        try:
            customer_message = _(
                "marzban_modify_user.customer_renew_notification",
                username=f"`{username}`",
                days=renewal_duration_days,
                gb=int(data_limit_gb)
            )
            await context.bot.send_message(customer_id, customer_message, parse_mode=ParseMode.MARKDOWN)
            customer_notified = True
        except Exception as e:
            LOGGER.error(f"User {username} renewed, but failed to notify customer {customer_id}: {e}")

    # --- Step 5: Show Final Success Message to Admin ---
    if customer_notified:
        success_message = _("marzban_modify_user.renew_successful_admin_and_customer", username=f"`{username}`")
    else:
        # This will be shown if customer is not linked or if sending message to them failed
        success_message = _("marzban_modify_user.renew_successful_admin_only", username=f"`{username}`")
    
    await show_user_details_panel(
        context=context, 
        chat_id=query.message.chat_id, 
        message_id=query.message.message_id,
        username=username, 
        list_type=context.user_data.get('current_list_type', 'all'),
        page_number=context.user_data.get('current_page', 1), 
        success_message=success_message
    )