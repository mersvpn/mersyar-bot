# FILE: modules/customer/actions/service.py (REFACTORED FOR RESPONSIVENESS)

import datetime
import jdatetime
import logging
import asyncio

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from config import config
from shared.translator import _
from shared.keyboards import get_customer_main_menu_keyboard, get_admin_main_menu_keyboard
from modules.marzban.actions.api import get_user_data, reset_subscription_url_api
from modules.marzban.actions.constants import GB_IN_BYTES
from modules.marzban.actions.data_manager import normalize_username
from database.db_manager import (
    is_auto_renew_enabled,
    set_auto_renew_status,
    load_pricing_parameters,
    create_pending_invoice,
    is_account_test,
    get_linked_marzban_usernames, 
    unlink_user_from_telegram
)
from modules.payment.actions.creation import send_custom_plan_invoice
from shared.keyboards import get_back_to_main_menu_keyboard

LOGGER = logging.getLogger(__name__)

CHOOSE_SERVICE, DISPLAY_SERVICE, CONFIRM_RESET_SUB, CONFIRM_DELETE = range(4)
PROMPT_FOR_DATA_AMOUNT, CONFIRM_DATA_PURCHASE = range(4, 6)
ITEMS_PER_PAGE = 8

# =============================================================================
#  BACKGROUND TASK (NEW LOGIC)
#  This function contains all the slow network operations.
# =============================================================================
async def _fetch_and_display_services(context: ContextTypes.DEFAULT_TYPE, user_id: int, loading_message):
    """
    This is the background task. It fetches all data from Marzban, filters it,
    and then edits the "Loading..." message with the final result.
    """
    try:
        linked_usernames_raw = await get_linked_marzban_usernames(user_id)
        if not linked_usernames_raw:
            await loading_message.edit_text(_("customer.customer_service.no_service_linked"))
            return

        tasks = [get_user_data(username) for username in linked_usernames_raw]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_linked_accounts = []
        dead_links_to_cleanup = []

        for i, result in enumerate(results):
            username_raw = linked_usernames_raw[i]
            if isinstance(result, dict) and "error" not in result and result is not None:
                valid_linked_accounts.append(result)
            else:
                dead_links_to_cleanup.append(normalize_username(username_raw))
                if not isinstance(result, Exception):
                    LOGGER.warning(f"Failed to get data for user '{username_raw}': {result}")

        if dead_links_to_cleanup:
            LOGGER.info(f"Cleaning up {len(dead_links_to_cleanup)} dead links for user {user_id}: {dead_links_to_cleanup}")
            cleanup_tasks = [unlink_user_from_telegram(dead_username) for dead_username in dead_links_to_cleanup]
            await asyncio.gather(*cleanup_tasks)
        
        is_test_tasks = [is_account_test(acc['username']) for acc in valid_linked_accounts]
        is_test_results = await asyncio.gather(*is_test_tasks)
        
        final_accounts_to_show = [acc for i, acc in enumerate(valid_linked_accounts) if not is_test_results[i]]
        
        if not final_accounts_to_show:
            await loading_message.edit_text(_("customer.customer_service.no_valid_service_found"))
            return
        
        if len(final_accounts_to_show) == 1:
            original_username = final_accounts_to_show[0]['username']
            # Directly call display_service_details to edit the message
            await display_service_details(user_id, loading_message, context, original_username)
        else:
            sorted_services = sorted(final_accounts_to_show, key=lambda u: u['username'].lower())
            context.user_data['services_list'] = sorted_services
            reply_markup = await _build_paginated_service_keyboard(sorted_services, page=0)
            await loading_message.edit_text(_("customer.customer_service.multiple_services_prompt"), reply_markup=reply_markup)

    except asyncio.CancelledError:
        LOGGER.info(f"Service loading for user {user_id} was cancelled by the user.")
        # The message will be deleted by the cancellation handler, so no need to edit it.
    except Exception as e:
        LOGGER.error(f"An error occurred while fetching services for user {user_id}: {e}", exc_info=True)
        try:
            await loading_message.edit_text(_("customer.customer_service.panel_connection_error"))
        except Exception:
            pass # Message might have been deleted already
    finally:
        # Clean up the task from user_data once it's finished or cancelled
        context.user_data.pop('service_loader_task', None)


# =============================================================================
#  PAGINATION HELPER FUNCTIONS (UNCHANGED)
# =============================================================================
async def _build_paginated_service_keyboard(services: list, page: int = 0) -> InlineKeyboardMarkup:
    # This function is unchanged
    start_index = page * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE
    keyboard = []
    for user in services[start_index:end_index]:
        if user.get('status') == 'active':
            button_text = _("keyboards.buttons.service_status_active", username=user['username'])
        else:
            button_text = _("keyboards.buttons.service_status_inactive", username=user['username'])
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"select_service_{user['username']}")])
    nav_buttons = []
    total_pages = (len(services) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(_("keyboards.buttons.pagination_prev"), callback_data=f"page_back_{page-1}"))
    if total_pages > 1:
        page_indicator = _("keyboards.buttons.pagination_page", current=page + 1, total=total_pages)
        nav_buttons.append(InlineKeyboardButton(page_indicator, callback_data="noop"))
    if end_index < len(services):
        nav_buttons.append(InlineKeyboardButton(_("keyboards.buttons.pagination_next"), callback_data=f"page_fwd_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton(_("keyboards.buttons.cancel_and_return"), callback_data="customer_back_to_main_menu")])
    return InlineKeyboardMarkup(keyboard)

async def handle_service_page_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # This function is unchanged
    query = update.callback_query
    await query.answer()
    direction, page_str = query.data.split('_')[1:]
    page = int(page_str)
    services = context.user_data.get('services_list', [])
    if not services:
        await query.edit_message_text(_("customer.customer_service.service_list_error"))
        return ConversationHandler.END
    reply_markup = await _build_paginated_service_keyboard(services, page)
    await query.edit_message_text(_("customer.customer_service.multiple_services_prompt"), reply_markup=reply_markup)
    return CHOOSE_SERVICE

# =============================================================================
#  CORE FUNCTIONS
# =============================================================================

async def handle_my_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    (REWRITTEN) This is now the entry point. It's very fast.
    It sends a "Loading..." message, starts the background task, and immediately
    enters the conversation state, making the UI responsive.
    """
    user_id = update.effective_user.id
    loading_message = await update.message.reply_text(_("customer.customer_service.loading"))

    # Create and start the background task
    task = asyncio.create_task(
        _fetch_and_display_services(context=context, user_id=user_id, loading_message=loading_message)
    )
    
    # Store the task so we can cancel it if the user navigates away
    context.user_data['service_loader_task'] = task
    
    # Immediately enter the next state so the "Cancel" button works instantly
    return CHOOSE_SERVICE


# --- THE REST OF THE FILE REMAINS LARGELY UNCHANGED ---
# Only back_to_main_menu_customer needs a small modification to handle task cancellation.

async def display_service_details(user_id: int, message_to_edit, context: ContextTypes.DEFAULT_TYPE, marzban_username: str) -> int:
    from database.db_manager import get_user_note, is_auto_renew_enabled
    
    await message_to_edit.edit_text(text=_("customer.customer_service.getting_service_info", username=marzban_username))
    user_info = await get_user_data(marzban_username)
    # ... (rest of this function is unchanged)
    if not user_info or "error" in user_info:
        await message_to_edit.edit_text(_("customer.customer_service.service_not_found_in_panel"))
        return ConversationHandler.END

    is_active = user_info.get('status') == 'active'
    message = ""

    if is_active:
        usage_gb = (user_info.get('used_traffic') or 0) / GB_IN_BYTES
        limit_gb = (user_info.get('data_limit') or 0) / GB_IN_BYTES
        usage_str = f"{usage_gb:.2f} GB"
        if limit_gb > 0:
            usage_str += f" / {limit_gb:.0f} GB"
        else:
            usage_str += _("customer.customer_service.unlimited_usage_suffix")

        expire_str = _("customer.customer_service.unlimited_label")
        duration_str = _("customer.customer_service.duration_unknown")

        note_data = await get_user_note(normalize_username(marzban_username))
        if note_data and note_data.get('subscription_duration'):
            duration_str = _("customer.customer_service.duration_days", days=note_data['subscription_duration'])

        if user_info.get('expire'):
            expire_date = datetime.datetime.fromtimestamp(user_info['expire'])
            time_left = expire_date - datetime.datetime.now()
            if time_left.total_seconds() > 0:
                jalali_date = jdatetime.datetime.fromgregorian(datetime=expire_date)
                days_left_str = _("customer.customer_service.days_remaining", days=time_left.days)
                expire_str = f"{jalali_date.strftime('%Y/%m/%d')} ({days_left_str})"
            else:
                is_active = False
                expire_str = _("customer.customer_service.expired_status")
        
        sub_url = user_info.get('subscription_url', _("customer.customer_service.not_found"))
        
        message = _("customer.customer_service.active_details_message",
                    username=marzban_username,
                    usage=usage_str,
                    duration=duration_str,
                    expiry=expire_str,
                    sub_url=sub_url)
    
    if not is_active:
        message = _("customer.customer_service.inactive_details_message", username=marzban_username)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("keyboards.buttons.renew_this_service"), callback_data=f"customer_renew_request_{marzban_username}")],
            [InlineKeyboardButton(_("keyboards.buttons.back_to_main_menu"), callback_data="customer_back_to_main_menu")]
        ])
    else:
        auto_renew_is_on = await is_auto_renew_enabled(user_id, marzban_username)
        
        if auto_renew_is_on:
            auto_renew_text = _("keyboards.buttons.auto_renew_active")
            auto_renew_callback = f"toggle_autorenew_off:{marzban_username}"
        else:
            auto_renew_text = _("keyboards.buttons.auto_renew_inactive")
            auto_renew_callback = f"toggle_autorenew_on:{marzban_username}"

        keyboard_rows = [
            [
                InlineKeyboardButton(_("keyboards.buttons.request_renewal"), callback_data=f"customer_renew_request_{marzban_username}"),
                InlineKeyboardButton(_("keyboards.buttons.purchase_data"), callback_data=f"purchase_data_{marzban_username}")
            ],
            [
                InlineKeyboardButton(auto_renew_text, callback_data=auto_renew_callback)
            ],
            [
                InlineKeyboardButton(_("keyboards.buttons.reset_subscription"), callback_data=f"customer_reset_sub_{marzban_username}"),
                InlineKeyboardButton(_("keyboards.buttons.request_delete"), callback_data=f"request_delete_{marzban_username}")
            ],
            [InlineKeyboardButton(_("keyboards.buttons.back_to_main_menu"), callback_data="customer_back_to_main_menu")]
        ]
        keyboard = InlineKeyboardMarkup(keyboard_rows)

    await message_to_edit.edit_text(message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return DISPLAY_SERVICE


async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # This function is unchanged
    query = update.callback_query
    await query.answer()
    marzban_username = query.data.split('select_service_')[-1]
    user_id = query.from_user.id
    message_to_edit = query.message
    return await display_service_details(user_id, message_to_edit, context, marzban_username)


async def back_to_main_menu_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    (MODIFIED) This function now checks for and cancels the background task
    if the user decides to cancel while services are still loading.
    """
    query = update.callback_query
    await query.answer()
    
    # --- CHANGE START: Cancel the background task if it's running ---
    task = context.user_data.pop('service_loader_task', None)
    if task and not task.done():
        task.cancel()
    # --- CHANGE END ---
    
    user_id = update.effective_user.id
    message_text = _("general.operation_cancelled")
    
    if user_id in config.AUTHORIZED_USER_IDS:
        final_keyboard = get_admin_main_menu_keyboard()
    else:
        final_keyboard = await get_customer_main_menu_keyboard(user_id=user_id)
        
    try:
        await query.message.delete()
    except Exception:
        pass
        
    await context.bot.send_message(
        chat_id=user_id,
        text=message_text,
        reply_markup=final_keyboard
    )
    
    context.user_data.clear()
    return ConversationHandler.END


# ... All other functions (confirm_reset_subscription, execute_reset_subscription, etc.) remain completely unchanged ...
# They are copied here for completeness of the file.

async def confirm_reset_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    context.user_data['service_username'] = username
    text = _("customer.customer_service.reset_sub_warning")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("keyboards.buttons.reset_sub_confirm"), callback_data=f"do_reset_sub_{username}")],
        [InlineKeyboardButton(_("keyboards.buttons.reset_sub_cancel"), callback_data=f"select_service_{username}")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_RESET_SUB

async def execute_reset_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    if not username:
        await query.edit_message_text(_("general.errors.username_not_found"))
        return ConversationHandler.END
    await query.edit_message_text(_("customer.customer_service.resetting_sub_link", username=f"`{username}`"))
    success, result = await reset_subscription_url_api(username)
    if success:
        new_sub_url = result.get('subscription_url', _("customer.customer_service.not_found"))
        text = _("customer.customer_service.reset_sub_successful", sub_url=new_sub_url)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("keyboards.buttons.back_to_details"), callback_data=f"select_service_{username}")]])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        text = _("customer.customer_service.reset_sub_failed", error=result)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("keyboards.buttons.back_to_details"), callback_data=f"select_service_{username}")]])
        await query.edit_message_text(text, reply_markup=keyboard)
    return DISPLAY_SERVICE

async def request_delete_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    text = _("customer.customer_service.delete_request_warning", username=f"`{username}`")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("keyboards.buttons.delete_confirm"), callback_data=f"confirm_delete_{username}")],
        [InlineKeyboardButton(_("keyboards.buttons.delete_cancel"), callback_data=f"select_service_{username}")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_DELETE

async def confirm_delete_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    user = update.effective_user
    await query.edit_message_text(_("customer.customer_service.delete_request_sent"))
    if config.AUTHORIZED_USER_IDS:
        user_info_str = f"{user.full_name}"
        if user.username: user_info_str += f" (@{user.username})"
        user_info_str += f"\nUser ID: `{user.id}`"
        message_to_admin = _("customer.customer_service.delete_request_admin_notification", user_info=user_info_str, username=f"`{username}`")
        admin_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(_("keyboards.buttons.confirm_delete_admin"), callback_data=f"delete_{username}")]])
        for admin_id in config.AUTHORIZED_USER_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=message_to_admin, reply_markup=admin_keyboard, parse_mode=ParseMode.MARKDOWN)
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
        await query.edit_message_text(_("customer.customer_service.purchase_data_not_configured"))
        return ConversationHandler.END
    text = _("customer.customer_service.purchase_data_prompt", username=f"`{marzban_username}`")
    await query.message.delete()
    await context.bot.send_message(chat_id=query.message.chat_id, text=text, reply_markup=get_back_to_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
    return PROMPT_FOR_DATA_AMOUNT

async def calculate_price_and_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        volume_gb = int(update.message.text.strip())
        if volume_gb <= 0: raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(_("customer.customer_service.invalid_number_input"))
        return PROMPT_FOR_DATA_AMOUNT
    pricing_params = await load_pricing_parameters()
    tiers = sorted(pricing_params.get("tiers", []), key=lambda x: x['volume_limit_gb'])
    price_per_gb = 0
    if tiers:
        for tier in tiers:
            if volume_gb <= tier['volume_limit_gb']:
                price_per_gb = tier['price_per_gb']
                break
        if price_per_gb == 0: price_per_gb = tiers[-1]['price_per_gb']
    if price_per_gb == 0:
        await update.message.reply_text(_("customer.customer_service.pricing_system_error"))
        return ConversationHandler.END
    total_price = volume_gb * price_per_gb
    username = context.user_data.get('purchase_data_username')
    context.user_data['purchase_data_details'] = {
    "volume": volume_gb, 
    "price": total_price, 
    "plan_type": "data_top_up", 
    "username": username,
    "invoice_type": "DATA_TOP_UP"  # <-- ADD THIS KEY
}
    text = _("customer.customer_service.data_purchase_invoice_preview", username=f"`{username}`", volume=volume_gb, price=total_price)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("keyboards.buttons.confirm_and_get_invoice"), callback_data="confirm_data_purchase_final")],
        [InlineKeyboardButton(_("keyboards.buttons.cancel"), callback_data=f"select_service_{username}")]])
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_DATA_PURCHASE

async def generate_data_purchase_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(_("customer.customer_service.generating_invoice"))
    user_id = query.from_user.id
    purchase_details = context.user_data.get('purchase_data_details')
    if not purchase_details:
        purchase_details['invoice_type'] = 'DATA_TOP_UP'
        await query.edit_message_text(_("customer.customer_service.purchase_info_not_found"))
        return ConversationHandler.END
    price = purchase_details.get('price')
    invoice_id = await create_pending_invoice(user_id, purchase_details, price)
    if not invoice_id:
        await query.edit_message_text(_("customer.customer_service.system_error_retry"))
        return ConversationHandler.END
    await query.message.delete()
    invoice_display_details = {"volume": f"+{purchase_details['volume']} GB", "duration": _("customer.customer_service.data_top_up_label"), "price": price}
    await send_custom_plan_invoice(update, context, invoice_display_details, invoice_id)
    context.user_data.clear()
    return ConversationHandler.END

async def toggle_auto_renew(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    
    try:
        prefix, marzban_username = query.data.split(':', 1)
        action = prefix.split('_')[-1]
        new_status = (action == "on")
    except (ValueError, IndexError):
        LOGGER.error(f"Invalid callback data for toggle_auto_renew: {query.data}")
        await query.answer(_("general.errors.internal_error"), show_alert=True)
        return DISPLAY_SERVICE

    # Show the modern, fading pop-up message to the user
    if new_status:
        await query.answer(_("customer.customer_service.auto_renew_activated_alert"), show_alert=False)
    else:
        await query.answer(_("customer.customer_service.auto_renew_deactivated_alert"), show_alert=False)

    user_id = update.effective_user.id
    await set_auto_renew_status(user_id, marzban_username, new_status)
    
    # Refresh the service details panel to show the updated button
    message_to_edit = query.message
    return await display_service_details(user_id, message_to_edit, context, marzban_username)