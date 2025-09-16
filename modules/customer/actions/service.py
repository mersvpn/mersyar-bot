# FILE: modules/customer/actions/service.py (REVISED FOR I18N)

import datetime
import jdatetime
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from config import config
# Import the translator
from shared.translator import _
from shared.keyboards import get_customer_main_menu_keyboard, get_admin_main_menu_keyboard
from modules.marzban.actions.api import get_user_data, reset_subscription_url_api, get_all_users
from modules.marzban.actions.constants import GB_IN_BYTES
from modules.marzban.actions.data_manager import normalize_username
from database.db_manager import load_pricing_parameters, create_pending_invoice
from modules.financials.actions.payment import send_custom_plan_invoice
from shared.keyboards import get_back_to_main_menu_keyboard

LOGGER = logging.getLogger(__name__)

CHOOSE_SERVICE, DISPLAY_SERVICE, CONFIRM_RESET_SUB, CONFIRM_DELETE = range(4)
PROMPT_FOR_DATA_AMOUNT, CONFIRM_DATA_PURCHASE = range(4, 6)
ITEMS_PER_PAGE = 8

# =============================================================================
#  PAGINATION HELPER FUNCTIONS (REVISED FOR I18N)
# =============================================================================
async def _build_paginated_service_keyboard(services: list, page: int = 0) -> InlineKeyboardMarkup:
    """Builds a paginated keyboard for services."""
    start_index = page * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    
    keyboard = []
    
    for user in services[start_index:end_index]:
        if user.get('status') == 'active':
            button_text = _("buttons.service_status_active", username=user['username'])
        else:
            button_text = _("buttons.service_status_inactive", username=user['username'])
        
        keyboard.append([
            InlineKeyboardButton(
                button_text, 
                callback_data=f"select_service_{user['username']}"
            )
        ])
        
    nav_buttons = []
    total_pages = (len(services) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(_("buttons.pagination_prev"), callback_data=f"page_back_{page-1}"))
    
    if total_pages > 1:
        page_indicator = _("buttons.pagination_page", current=page + 1, total=total_pages)
        nav_buttons.append(InlineKeyboardButton(page_indicator, callback_data="noop"))

    if end_index < len(services):
        nav_buttons.append(InlineKeyboardButton(_("buttons.pagination_next"), callback_data=f"page_fwd_{page+1}"))
        
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton(_("buttons.cancel_and_return"), callback_data="customer_back_to_main_menu")])
    return InlineKeyboardMarkup(keyboard)

async def handle_service_page_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles clicks on 'next' and 'previous' buttons."""
    query = update.callback_query
    await query.answer()

    direction, page_str = query.data.split('_')[1:]
    page = int(page_str)

    services = context.user_data.get('services_list', [])
    if not services:
        await query.edit_message_text(_("customer_service.service_list_error"))
        return ConversationHandler.END

    reply_markup = await _build_paginated_service_keyboard(services, page)
    await query.edit_message_text(
        _("customer_service.multiple_services_prompt"), 
        reply_markup=reply_markup
    )
    return CHOOSE_SERVICE

# =============================================================================
#  CORE FUNCTIONS (REVISED FOR I18N)
# =============================================================================

async def display_service_details(update: Update, context: ContextTypes.DEFAULT_TYPE, marzban_username: str) -> int:
    from shared.translator import _ # Local import
    from database.db_manager import get_user_note
    
    target_message = update.callback_query.message if update.callback_query else update.message
    
    await context.bot.edit_message_text(
        chat_id=target_message.chat_id,
        message_id=target_message.message_id,
        text=_("customer_service.getting_service_info", username=marzban_username)
    )

    user_info = await get_user_data(marzban_username)
    if not user_info or "error" in user_info:
        await target_message.edit_text(_("customer_service.service_not_found_in_panel"))
        return ConversationHandler.END

    is_active = user_info.get('status') == 'active'

    if is_active:
        usage_gb = (user_info.get('used_traffic') or 0) / GB_IN_BYTES
        limit_gb = (user_info.get('data_limit') or 0) / GB_IN_BYTES
        usage_str = f"{usage_gb:.2f} GB"
        if limit_gb > 0:
            usage_str += f" / {limit_gb:.0f} GB"
        else:
            usage_str += _("customer_service.unlimited_usage_suffix")

        expire_str = _("customer_service.unlimited_label")
        duration_str = _("customer_service.duration_unknown")

        note_data = await get_user_note(normalize_username(marzban_username))
        if note_data and note_data.get('subscription_duration'):
            duration_str = _("customer_service.duration_days", days=note_data['subscription_duration'])

        if user_info.get('expire'):
            expire_date = datetime.datetime.fromtimestamp(user_info['expire'])
            time_left = expire_date - datetime.datetime.now()
            if time_left.total_seconds() > 0:
                jalali_date = jdatetime.datetime.fromgregorian(datetime=expire_date)
                days_left_str = _("customer_service.days_remaining", days=time_left.days)
                expire_str = f"{jalali_date.strftime('%Y/%m/%d')} ({days_left_str})"
            else:
                is_active = False 
                expire_str = _("customer_service.expired_status")
        
        sub_url = user_info.get('subscription_url', _("customer_service.not_found"))
        
        # ✨✨✨ KEY FIX HERE ✨✨✨
        # All f-string formatting with backticks is removed.
        # Python now only passes raw data to the translator.
        message = _("customer_service.active_details_message",
                    username=marzban_username,
                    usage=usage_str,
                    duration=duration_str,
                    expiry=expire_str,
                    sub_url=sub_url)
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(_("buttons.request_renewal"), callback_data=f"customer_renew_request_{marzban_username}"),
                InlineKeyboardButton(_("buttons.purchase_data"), callback_data=f"purchase_data_{marzban_username}")
            ],
            [
                InlineKeyboardButton(_("buttons.reset_subscription"), callback_data=f"customer_reset_sub_{marzban_username}"),
                InlineKeyboardButton(_("buttons.request_delete"), callback_data=f"request_delete_{marzban_username}")
            ],
            [InlineKeyboardButton(_("buttons.back_to_main_menu"), callback_data="customer_back_to_main_menu")]
        ])
    
    if not is_active:
        # This part also needs fixing for consistency
        message = _("customer_service.inactive_details_message", username=f"`{marzban_username}`")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("buttons.renew_this_service"), callback_data=f"customer_renew_request_{marzban_username}")],
            [InlineKeyboardButton(_("buttons.back_to_main_menu"), callback_data="customer_back_to_main_menu")]
        ])

    await target_message.edit_text(message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return DISPLAY_SERVICE

async def handle_my_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database.db_manager import get_linked_marzban_usernames, unlink_user_from_telegram
    
    user_id = update.effective_user.id
    loading_message = await update.message.reply_text(_("customer_service.loading"))

    linked_usernames_raw = await get_linked_marzban_usernames(user_id)
    if not linked_usernames_raw:
        await loading_message.edit_text(_("customer_service.no_service_linked"))
        return ConversationHandler.END

    all_marzban_users_list = await get_all_users()
    if all_marzban_users_list is None:
        await loading_message.edit_text(_("customer_service.panel_connection_error"))
        return ConversationHandler.END
        
    marzban_usernames_set = {normalize_username(u['username']) for u in all_marzban_users_list if u.get('username')}
    all_marzban_users_dict = {normalize_username(u['username']): u for u in all_marzban_users_list if u.get('username')}

    valid_linked_accounts = []
    dead_links_to_cleanup = []

    for username_raw in linked_usernames_raw:
        normalized = normalize_username(username_raw)
        if normalized in marzban_usernames_set:
            valid_linked_accounts.append(all_marzban_users_dict[normalized])
        else:
            dead_links_to_cleanup.append(normalized)

    if dead_links_to_cleanup:
        LOGGER.info(f"Cleaning up {len(dead_links_to_cleanup)} dead links for user {user_id}: {dead_links_to_cleanup}")
        for dead_username in dead_links_to_cleanup:
            await unlink_user_from_telegram(dead_username)

    if not valid_linked_accounts:
        await loading_message.edit_text(_("customer_service.no_valid_service_found"))
        return ConversationHandler.END

    if len(valid_linked_accounts) == 1:
        class DummyQuery:
            def __init__(self, message): self.message = message
        dummy_update = type('obj', (object,), {'callback_query': DummyQuery(loading_message)})
        original_username = valid_linked_accounts[0]['username']
        return await display_service_details(dummy_update, context, original_username)

    sorted_services = sorted(valid_linked_accounts, key=lambda u: u['username'].lower())
    context.user_data['services_list'] = sorted_services

    reply_markup = await _build_paginated_service_keyboard(sorted_services, page=0)
    
    await loading_message.edit_text(_("customer_service.multiple_services_prompt"), reply_markup=reply_markup)
    return CHOOSE_SERVICE

async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    marzban_username = query.data.split('select_service_')[-1]
    return await display_service_details(update, context, marzban_username)

async def confirm_reset_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    context.user_data['service_username'] = username
    text = _("customer_service.reset_sub_warning")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("buttons.reset_sub_confirm"), callback_data=f"do_reset_sub_{username}")],
        [InlineKeyboardButton(_("buttons.reset_sub_cancel"), callback_data=f"select_service_{username}")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_RESET_SUB

async def execute_reset_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _ # Local import
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    if not username:
        await query.edit_message_text(_("errors.username_not_found"))
        return ConversationHandler.END

    await query.edit_message_text(_("customer_service.resetting_sub_link", username=f"`{username}`"))
    success, result = await reset_subscription_url_api(username)

    if success:
        new_sub_url = result.get('subscription_url', _("customer_service.not_found"))
        
        # ✨✨✨ KEY FIX HERE ✨✨✨
        # Removed the f-string and backticks. Now passing raw data.
        text = _("customer_service.reset_sub_successful", sub_url=new_sub_url)
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("buttons.back_to_details"), callback_data=f"select_service_{username}")]])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        text = _("customer_service.reset_sub_failed", error=result)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("buttons.back_to_details"), callback_data=f"select_service_{username}")]])
        await query.edit_message_text(text, reply_markup=keyboard)
        
    return DISPLAY_SERVICE
async def back_to_main_menu_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    # Text is handled by the `send_main_menu` function now.
    message_text = _("general.operation_cancelled")
    
    if user_id in config.AUTHORIZED_USER_IDS:
        final_keyboard = get_admin_main_menu_keyboard()
    else:
        final_keyboard = get_customer_main_menu_keyboard()

    await query.message.delete()
    await context.bot.send_message(
        chat_id=user_id,
        text=message_text,
        reply_markup=final_keyboard
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def request_delete_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    text = _("customer_service.delete_request_warning", username=f"`{username}`")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("buttons.delete_confirm"), callback_data=f"confirm_delete_{username}")],
        [InlineKeyboardButton(_("buttons.delete_cancel"), callback_data=f"select_service_{username}")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_DELETE

async def confirm_delete_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from config import config
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    user = update.effective_user
    await query.edit_message_text(_("customer_service.delete_request_sent"))
    
    if config.AUTHORIZED_USER_IDS:
        user_info_str = f"{user.full_name}"
        if user.username:
            user_info_str += f" (@{user.username})"
        user_info_str += f"\nUser ID: `{user.id}`"
        
        message_to_admin = _("customer_service.delete_request_admin_notification", 
                             user_info=user_info_str, 
                             username=f"`{username}`")
        
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("buttons.confirm_delete_admin"), callback_data=f"delete_{username}")],
        ])

        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=message_to_admin,
                    reply_markup=admin_keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                LOGGER.error(f"Failed to send delete request to admin {admin_id} for {username}: {e}", exc_info=True)
    return ConversationHandler.END

async def start_data_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    marzban_username = query.data.split('purchase_data_')[-1]
    context.user_data['purchase_data_username'] = marzban_username
    
    pricing_params = await load_pricing_parameters()
    if not pricing_params.get("tiers"):
        await query.edit_message_text(_("customer_service.purchase_data_not_configured"))
        return ConversationHandler.END

    text = _("customer_service.purchase_data_prompt", username=f"`{marzban_username}`")
    
    await query.message.delete()
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        reply_markup=get_back_to_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    
    return PROMPT_FOR_DATA_AMOUNT

async def calculate_price_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        volume_gb = int(update.message.text.strip())
        if volume_gb <= 0:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(_("customer_service.invalid_number_input"))
        return PROMPT_FOR_DATA_AMOUNT

    pricing_params = await load_pricing_parameters()
    tiers = sorted(pricing_params.get("tiers", []), key=lambda x: x['volume_limit_gb'])
    
    price_per_gb = 0
    if tiers:
        for tier in tiers:
            if volume_gb <= tier['volume_limit_gb']:
                price_per_gb = tier['price_per_gb']
                break
        if price_per_gb == 0:
            price_per_gb = tiers[-1]['price_per_gb']
    
    if price_per_gb == 0:
        await update.message.reply_text(_("customer_service.pricing_system_error"))
        return ConversationHandler.END

    total_price = volume_gb * price_per_gb
    username = context.user_data.get('purchase_data_username')
    
    context.user_data['purchase_data_details'] = {
        "volume": volume_gb,
        "price": total_price,
        "plan_type": "data_top_up",
        "username": username
    }

    text = _("customer_service.data_purchase_invoice_preview",
             username=f"`{username}`",
             volume=volume_gb,
             price=total_price)
             
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("buttons.confirm_and_get_invoice"), callback_data="confirm_data_purchase_final")],
        [InlineKeyboardButton(_("buttons.cancel"), callback_data=f"select_service_{username}")]
    ])
    
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_DATA_PURCHASE

async def generate_data_purchase_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_("customer_service.generating_invoice"))
    
    user_id = query.from_user.id
    purchase_details = context.user_data.get('purchase_data_details')
    
    if not purchase_details:
        await query.edit_message_text(_("customer_service.purchase_info_not_found"))
        return ConversationHandler.END

    price = purchase_details.get('price')
    invoice_id = await create_pending_invoice(user_id, purchase_details, price)
    
    if not invoice_id:
        await query.edit_message_text(_("customer_service.system_error_retry"))
        return ConversationHandler.END
        
    await query.message.delete()
    
    invoice_display_details = {
        "volume": f"+{purchase_details['volume']} GB",
        "duration": _("customer_service.data_top_up_label"),
        "price": price
    }
    await send_custom_plan_invoice(update, context, invoice_display_details, invoice_id)
    
    context.user_data.clear()
    return ConversationHandler.END