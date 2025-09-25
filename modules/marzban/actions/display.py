# FILE: modules/marzban/actions/display.py (FINAL VERSION - MODIFIED FOR CALLBACK_TYPES)

import qrcode
import io
import time
import math
import datetime
import jdatetime
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from config import config
from shared.keyboards import get_user_management_keyboard
# --- MODIFIED: Import new callback type ---
from shared.callback_types import StartManualInvoice
from .constants import USERS_PER_PAGE, GB_IN_BYTES
from .api import get_all_users, get_user_data
from modules.general.actions import start as show_main_menu_action
from modules.auth import admin_only

LOGGER = logging.getLogger(__name__)

def _pad_string(input_str: str, max_len: int) -> str:
    return input_str + ' ' * (max_len - len(input_str))

def get_user_display_info(user: dict) -> tuple[str, str, bool, str, str]:
    from shared.translator import get as get_text
    username = user.get('username', 'N/A')
    sanitized_username = username.replace('`', '')
    
    status = user.get('status', 'disabled')
    used_traffic = user.get('used_traffic') or 0
    data_limit = user.get('data_limit') or 0
    expire_timestamp = user.get('expire')
    online_at = user.get('online_at')

    prefix = get_text("marzban.marzban_display.status_active")
    is_online = False
    days_left_str = get_text("marzban.marzban_display.infinite")
    data_left_str = get_text("marzban.marzban_display.infinite")

    if online_at:
        try:
            online_at_dt = datetime.datetime.fromisoformat(online_at.replace("Z", "+00:00"))
            if (datetime.datetime.now(datetime.timezone.utc) - online_at_dt).total_seconds() < 180:
                is_online = True
                prefix = get_text("marzban.marzban_display.status_online")
        except (ValueError, TypeError): pass

    if status != 'active' or (expire_timestamp and datetime.datetime.fromtimestamp(expire_timestamp) < datetime.datetime.now()):
        prefix = get_text("marzban.marzban_display.status_inactive")
        days_left_str = get_text("marzban.marzban_display.expired")
    else:
        is_warning = False
        if expire_timestamp:
            time_left = datetime.datetime.fromtimestamp(expire_timestamp) - datetime.datetime.now()
            days_left_val = time_left.days + (1 if time_left.seconds > 0 else 0)
            days_left_str = get_text("marzban.marzban_display.days_left", days=days_left_val)
            if 0 < days_left_val <= 3:
                is_warning = True
        
        if data_limit > 0:
            data_left_gb = (data_limit - used_traffic) / GB_IN_BYTES
            data_left_str = get_text("marzban.marzban_display.data_left_gb", gb=data_left_gb)
            if data_left_gb < 1:
                is_warning = True
        
        if is_warning and not is_online:
            prefix = get_text("marzban.marzban_display.status_warning")
            
    return prefix, sanitized_username, is_online, days_left_str, data_left_str

# ----------------- START OF MODIFIED CODE -----------------

# ----------------- START OF FINAL CODE -----------------
def _get_status_emoji(user: dict) -> str:
    """Determines the correct status emoji for a user based on their state."""
    from shared.translator import get as get_text
    
    # 1. Check for recent online activity first (highest priority)
    online_at = user.get('online_at')
    if online_at:
        try:
            # FIX: Use strptime for the specific format without timezone info
            # Assuming the panel time is in UTC
            online_at_dt = datetime.datetime.strptime(online_at, "%Y-%m-%dT%H:%M:%S")
            online_at_dt = online_at_dt.replace(tzinfo=datetime.timezone.utc)

            # If online in the last 3 minutes
            if (datetime.datetime.now(datetime.timezone.utc) - online_at_dt).total_seconds() < 180:
                return "🟢"
        except (ValueError, TypeError):
            pass # Ignore malformed dates

    # 2. If not recently online, determine status based on usage and expiry
    status = user.get('status', 'disabled')
    expire_timestamp = user.get('expire')

    # Inactive/Expired status
    if status != 'active' or (expire_timestamp and datetime.datetime.fromtimestamp(expire_timestamp) < datetime.datetime.now()):
        return "🔴"

    # Warning status
    is_warning = False
    if expire_timestamp:
        time_left = datetime.datetime.fromtimestamp(expire_timestamp) - datetime.datetime.now()
        days_left_val = time_left.days
        if 0 <= days_left_val <= 3: # Check for 0 to 3 days left
            is_warning = True
    
    data_limit = user.get('data_limit') or 0
    if data_limit > 0:
        used_traffic = user.get('used_traffic') or 0
        data_left_gb = (data_limit - used_traffic) / GB_IN_BYTES
        if data_left_gb < 1:
            is_warning = True
            
    if is_warning:
        return "🟡"
        
    # 3. If active, not in warning, and not recently online
    return "⚪️"
# -----------------  END OF FINAL CODE  -----------------


def build_users_keyboard(users: list, current_page: int, total_pages: int, list_type: str) -> InlineKeyboardMarkup:
    """Builds a modern, three-column keyboard for displaying users."""
    from shared.translator import get as get_text
    
    keyboard_rows = []
    
    # --- Create 3-column user buttons ---
    # This loop processes users in chunks of 3
    for i in range(0, len(users), 3):
        row = []
        # Get a slice of up to 3 users for the current row
        for user in users[i : i + 3]:
            username = user.get('username', 'N/A')
            status_emoji = _get_status_emoji(user)
            
            # Button text is now clean: just emoji + username
            button_text = f"{status_emoji} {username}"
            
            # Callback data remains the same for functionality
            callback_data = f"user_details_{username}_{list_type}_{current_page}"
            
            row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        keyboard_rows.append(row)

    # --- Create navigation row ---
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            get_text("marzban.marzban_display.pagination_prev"), 
            callback_data=f"show_users_page_{list_type}_{current_page - 1}"
        ))
        
    # Page info button (always shown if there are multiple pages)
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(
            get_text("marzban.marzban_display.pagination_page_info", current=current_page, total=total_pages), 
            callback_data="noop" # no-operation, just a label
        ))
        
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            get_text("marzban.marzban_display.pagination_next"), 
            callback_data=f"show_users_page_{list_type}_{current_page + 1}"
        ))

    if nav_row:
        keyboard_rows.append(nav_row)
        
    # --- Create close button row ---
    keyboard_rows.append([
        InlineKeyboardButton(get_text("marzban.marzban_display.pagination_close"), callback_data="close_pagination")
    ])
    
    return InlineKeyboardMarkup(keyboard_rows)

# -----------------  END OF MODIFIED CODE  -----------------
@admin_only
async def show_user_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import get as get_text
    await update.message.reply_text(get_text("marzban.marzban_display.user_management_section"), reply_markup=get_user_management_keyboard())

async def _list_users_base(update: Update, context: ContextTypes.DEFAULT_TYPE, list_type: str, page: int = 1):
    from shared.translator import get as get_text
    is_callback = update.callback_query is not None
    message = update.callback_query.message if is_callback else await update.message.reply_text(get_text("marzban.marzban_display.loading"))
    
    if list_type != 'search':
        context.user_data.pop('last_search_results', None)
    
    if is_callback:
        await update.callback_query.answer()
    else:
        await message.edit_text(get_text("marzban.marzban_display.fetching_users"))
    
    target_users = []
    
    try:
        if list_type == 'search':
            title_text = get_text("marzban.marzban_display.search_results_title")
            not_found_text = get_text("marzban.marzban_display.no_search_results")
            target_users = context.user_data.get('last_search_results', [])
        else:
            title_text = get_text("marzban.marzban_display.warning_list_title") if list_type == 'warning' else get_text("marzban.marzban_display.all_users_list_title")
            not_found_text = get_text("marzban.marzban_display.no_warning_users") if list_type == 'warning' else get_text("marzban.marzban_display.no_users_in_panel")
            
            all_users = await get_all_users()
            if all_users is None:
                await message.edit_text(get_text("marzban.marzban_display.panel_connection_error")); return
            
            if list_type == 'warning':
                warning_users = []
                warning_status = get_text("marzban.marzban_display.status_warning")
                inactive_status = get_text("marzban.marzban_display.status_inactive")
                for u in all_users:
                    prefix, _, is_online, _, _ = get_user_display_info(u)
                    if not is_online and prefix in [warning_status, inactive_status]:
                        warning_users.append(u)
                target_users = sorted(warning_users, key=lambda u: u.get('username','').lower())
            else:
                target_users = sorted(all_users, key=lambda u: u.get('username','').lower())

        if not target_users:
            await message.edit_text(not_found_text); return
            
        total_pages = math.ceil(len(target_users) / USERS_PER_PAGE)
        page = max(1, min(page, total_pages))
        start_index = (page - 1) * USERS_PER_PAGE
        page_users = target_users[start_index : start_index + USERS_PER_PAGE]
        
        keyboard = build_users_keyboard(page_users, page, total_pages, list_type)
        safe_title = escape_markdown(get_text("marzban.marzban_display.page_title", title=title_text, page=page), version=2)
        await message.edit_text(safe_title, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)

    except Exception as e:
        LOGGER.error(f"Error in _list_users_base: {e}", exc_info=True)
        from shared.translator import get as get_text
        await message.edit_text(get_text("marzban.marzban_display.list_display_error"))

@admin_only
async def list_all_users_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _list_users_base(update, context, list_type='all')

@admin_only
async def list_warning_users_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _list_users_base(update, context, list_type='warning')

async def update_user_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _list_users_base(update, context, list_type=update.callback_query.data.split('_')[-2], page=int(update.callback_query.data.split('_')[-1]))

async def show_user_details_panel(context: ContextTypes.DEFAULT_TYPE, chat_id: int, username: str, list_type: str, page_number: int, success_message: str = None, message_id: int = None) -> None:
    from shared.translator import get as get_text
    user_info = await get_user_data(username)
    if not user_info:
        if message_id:
            try:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=get_text("marzban.marzban_display.user_not_found"))
            except Exception:
                await context.bot.send_message(chat_id=chat_id, text=get_text("marzban.marzban_display.user_not_found"))
        return

    online_status = get_text("marzban.marzban_display.offline")
    if user_info.get('online_at'):
        try:
            # FIX: Use strptime to match the new date format
            online_at_dt = datetime.datetime.strptime(user_info['online_at'], "%Y-%m-%dT%H:%M:%S")
            online_at_dt = online_at_dt.replace(tzinfo=datetime.timezone.utc)
            if (datetime.datetime.now(datetime.timezone.utc) - online_at_dt).total_seconds() < 180:
                online_status = get_text("marzban.marzban_display.online")
        except (ValueError, TypeError):
            pass
        
    used_gb = (user_info.get('used_traffic') or 0) / GB_IN_BYTES
    limit_gb = (user_info.get('data_limit') or 0) / GB_IN_BYTES
    usage_str = f"{used_gb:.2f} GB / " + (f"{limit_gb:.0f} GB" if limit_gb > 0 else get_text("marzban.marzban_display.unlimited"))
    
    expire_str = get_text("marzban.marzban_display.unlimited")
    if user_info.get('expire'):
        expire_dt = datetime.datetime.fromtimestamp(user_info['expire'])
        if expire_dt > datetime.datetime.now():
            jalali_date = jdatetime.datetime.fromgregorian(datetime=expire_dt)
            days_left = (expire_dt - datetime.datetime.now()).days
            expire_str = f"{jalali_date.strftime('%Y/%m/%d')} (" + get_text("marzban.marzban_display.days_remaining", days=days_left) + ")"
        else:
            expire_str = get_text("marzban.marzban_display.expired")
            
    message_text = ""
    if success_message:
        message_text += f"{success_message}\n{'-'*20}\n"
    
    message_text += get_text("marzban.marzban_display.user_details_title", username=username)
    message_text += f"{get_text('marzban.marzban_display.user_status_label')} {online_status}\n"
    message_text += f"{get_text('marzban.marzban_display.user_usage_label')} {usage_str}\n"
    message_text += f"{get_text('marzban.marzban_display.user_expiry_label')} `{expire_str}`"
    
    back_button_callback = f"list_subs_page_{page_number}" if list_type == 'subs' else f"show_users_page_{list_type}_{page_number}"
    back_button_text = get_text("marzban.marzban_display.back_to_subs_list") if list_type == 'subs' else get_text("marzban.marzban_display.back_to_users_list")
    
    # --- MODIFIED: Use StartManualInvoice for the "send invoice" button ---
    # NOTE: customer_id is not available here, so we use 0 as a placeholder.
    # The handler for StartManualInvoice will manage this by looking up the user in the DB.
    send_invoice_callback = StartManualInvoice(customer_id=0, username=username).to_string()

    keyboard_rows = [
        [InlineKeyboardButton(get_text("marzban.marzban_display.button_smart_renew"), callback_data=f"renew_{username}"), InlineKeyboardButton(get_text("marzban.marzban_display.button_send_invoice"), callback_data=send_invoice_callback)],
        [InlineKeyboardButton(get_text("marzban.marzban_display.button_add_data"), callback_data=f"add_data_{username}"), InlineKeyboardButton(get_text("marzban.marzban_display.button_add_days"), callback_data=f"add_days_{username}")],
        [InlineKeyboardButton(get_text("marzban.marzban_display.button_reset_traffic"), callback_data=f"reset_traffic_{username}"), InlineKeyboardButton(get_text("marzban.marzban_display.button_subscription_info"), callback_data=f"note_{username}")],
        [InlineKeyboardButton(get_text("marzban.marzban_display.button_subscription_link"), callback_data=f"sub_link_{username}"), InlineKeyboardButton(get_text("marzban.marzban_display.button_delete_user"), callback_data=f"delete_{username}")],
        [InlineKeyboardButton(back_button_text, callback_data=back_button_callback)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    if message_id:
        try:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await context.bot.send_message(chat_id=chat_id, text=message_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def show_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import get as get_text
    query = update.callback_query
    await query.answer()
    try:
        callback_data = query.data
        prefix_and_username, list_type, page_number_str = callback_data.rsplit('_', 2)
        page_number = int(page_number_str)
        username = prefix_and_username[len("user_details_"):]
        if not username: raise ValueError("Extracted username is empty.")
    except (ValueError, IndexError) as e:
        LOGGER.error(f"CRITICAL: Could not parse complex user_details callback_data '{query.data}': {e}")
        await query.edit_message_text(get_text("marzban.marzban_display.list_display_error"))
        return
    context.user_data['current_list_type'] = list_type
    context.user_data['current_page'] = page_number
    loading_message = None
    loading_text = get_text("marzban.marzban_display.getting_details_for", username=f"`{username}`")
    if query.message.photo:
        await query.message.delete()
        loading_message = await context.bot.send_message(chat_id=query.message.chat_id, text=loading_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.edit_message_text(loading_text, parse_mode=ParseMode.MARKDOWN)
        loading_message = query.message
    await show_user_details_panel(
        context=context, chat_id=loading_message.chat_id, message_id=loading_message.message_id,
        username=username, list_type=list_type, page_number=page_number
    )
    
async def close_pagination_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import get as get_text
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=get_text("marzban.marzban_display.back_to_user_management"),
        reply_markup=get_user_management_keyboard()
    )

async def handle_deep_link_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import get as get_text
    now = time.time()
    last_call = context.user_data.get('last_deeplink_call', 0)
    if now - last_call < 2: return
    context.user_data['last_deeplink_call'] = now
    if update.effective_user.id not in config.AUTHORIZED_USER_IDS:
        await show_main_menu_action(update, context); return
    try:
        if not context.args or not context.args[0].startswith('details_'):
            await show_main_menu_action(update, context); return
        username = context.args[0].split('_', 1)[1]
    except (IndexError, AttributeError):
        await update.message.reply_text(get_text("marzban.marzban_display.invalid_link"))
        await show_main_menu_action(update, context)
        return
    loading_msg = await update.message.reply_text(get_text("marzban.marzban_display.getting_details_for", username=f"`{username}`"), parse_mode=ParseMode.MARKDOWN)
    await show_user_details_panel(
        context=context, chat_id=loading_msg.chat_id, message_id=loading_msg.message_id,
        username=username, list_type='all', page_number=1
    )

def format_subscription_links(user_data: dict) -> str:
    from shared.translator import get as get_text
    links_text = ""
    subscription_url = user_data.get('subscription_url')
    if subscription_url:
        links_text += f"▫️ **لینک کلی:**\n`{subscription_url}`\n\n"
    inbounds = user_data.get('inbounds', {})
    if inbounds:
        for protocol, link_list in inbounds.items():
            if link_list:
                links_text += f"▫️ **لینک‌های {protocol.upper()}:**\n"
                for i, link in enumerate(link_list, 1): links_text += f"`{link}`\n"
                links_text += "\n"
    if not links_text:
        return get_text("marzban.marzban_display.sub_link_not_found")
    return links_text.strip()
    
async def send_subscription_qr_code_and_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from shared.translator import get as get_text
    query = update.callback_query
    await query.answer()
    try:
        username = query.data.split('_')[2]
    except IndexError:
        await query.edit_message_text(get_text("marzban.marzban_display.internal_error_username_not_found"))
        return
    user_data = await get_user_data(username)
    subscription_url = user_data.get('subscription_url')
    if not subscription_url:
        await query.edit_message_text(text=get_text("marzban.marzban_display.link_not_found_for_user", username=f"`{username}`"), parse_mode=ParseMode.MARKDOWN)
        return
    qr_image = qrcode.make(subscription_url)
    bio = io.BytesIO()
    bio.name = 'qrcode.png'
    qr_image.save(bio, 'PNG')
    bio.seek(0)
    caption = get_text("marzban.marzban_display.qr_caption", username=f"`{username}`", url=f"`{subscription_url}`")
    list_type = context.user_data.get('current_list_type', 'all')
    page_number = context.user_data.get('current_page', 1)
    back_button_callback = f"user_details_{username}_{list_type}_{page_number}"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(get_text("marzban.marzban_display.back_to_user_details"), callback_data=back_button_callback)
    ]])
    await query.message.delete()
    await context.bot.send_photo(
        chat_id=query.message.chat_id, photo=bio, caption=caption,
        reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN
    )