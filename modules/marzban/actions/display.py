# FILE: modules/marzban/actions/display.py
# (نسخه نهایی، کامل و بدون خطا)

import math
import datetime
import jdatetime
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from shared.keyboards import get_user_management_keyboard
from .constants import USERS_PER_PAGE, GB_IN_BYTES
from .api import get_all_users, get_user_data
from modules.general.actions import start as show_main_menu_action
from modules.auth import admin_only

LOGGER = logging.getLogger(__name__)

def get_user_display_info(user: dict) -> tuple[str, str]:
    username = user.get('username', 'N/A')
    status = user.get('status', 'disabled')
    # --- START OF FIX ---
    # Ensure used_traffic and data_limit are never None by defaulting to 0
    used_traffic = user.get('used_traffic') or 0
    data_limit = user.get('data_limit') or 0
    # --- END OF FIX ---
    expire_timestamp = user.get('expire')
    
    emojis, issues = [], []
    if status != 'active':
        emojis.append("🔴")
        issues.append("غیرفعال")
    
    if expire_timestamp and datetime.datetime.fromtimestamp(expire_timestamp) < datetime.datetime.now():
        if "🔴" not in emojis: emojis.append("🔴")
        issues.append("منقضی شده")

    if "🔴" not in emojis:
        if expire_timestamp:
            time_left = datetime.datetime.fromtimestamp(expire_timestamp) - datetime.datetime.now()
            if 0 < time_left.days <= 3:
                emojis.append("⏳")
                issues.append(f"{time_left.days+1} روز مانده")
        
        # This line is now safe from the TypeError
        if data_limit > 0 and (data_limit - used_traffic) < (1 * GB_IN_BYTES):
            if "⏳" not in emojis: emojis.append("📉")
            issues.append("حجم کم")
            
    if not emojis:
        emojis.append("✅")
        
    formatted_name = "".join(sorted(list(set(emojis)))) + f" {username}"
    details_text = ", ".join(issues) if issues else "فعال"
    return formatted_name, details_text

def build_users_keyboard(users: list, current_page: int, total_pages: int, list_type: str) -> InlineKeyboardMarkup:
    keyboard = []
    # Display users for the current page
    for i in range(0, len(users), 2):
        row = []
        user1 = users[i]
        formatted_name1, _ = get_user_display_info(user1)
        row.append(InlineKeyboardButton(formatted_name1, callback_data=f"user_details_{user1.get('username')}_{list_type}_{current_page}"))
        if i + 1 < len(users):
            user2 = users[i+1]
            formatted_name2, _ = get_user_display_info(user2)
            row.append(InlineKeyboardButton(formatted_name2, callback_data=f"user_details_{user2.get('username')}_{list_type}_{current_page}"))
        keyboard.append(row)
    
    # Navigation row
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"show_users_page_{list_type}_{current_page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(f"صفحه {current_page}/{total_pages}", callback_data="noop"))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"show_users_page_{list_type}_{current_page + 1}"))
    if nav_row:
        keyboard.append(nav_row)
        
    keyboard.append([InlineKeyboardButton("✖️ بستن", callback_data="close_pagination")])
    return InlineKeyboardMarkup(keyboard)

@admin_only
async def show_user_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the main user management menu."""
    await update.message.reply_text(
        "بخش مدیریت کاربران:",
        reply_markup=get_user_management_keyboard()
    )

async def _list_users_base(update: Update, context: ContextTypes.DEFAULT_TYPE, list_type: str, page: int = 1):
    is_callback = update.callback_query is not None
    message = update.callback_query.message if is_callback else await update.message.reply_text("در حال بارگذاری...")
    
    title_text = "⌛️ کاربران رو به اتمام:" if list_type == 'warning' else "👥 لیست کامل کاربران:"
    not_found_text = "✅ هیچ کاربر نیازمند توجهی یافت نشد." if list_type == 'warning' else "هیچ کاربری در پنل یافت نشد."
    
    if not is_callback:
        await message.edit_text("در حال دریافت و تحلیل لیست کاربران...")

    all_users = await get_all_users()
    if all_users is None:
        await message.edit_text("❌ خطا در ارتباط با سرور مرزبان."); return
    
    if not all_users:
        await message.edit_text(not_found_text); return

    if list_type == 'warning':
        target_users = sorted([u for u in all_users if "✅" not in get_user_display_info(u)[0]], key=lambda u: u.get('username','').lower())
    else:
        target_users = sorted(all_users, key=lambda u: u.get('username','').lower())

    if not target_users:
        await message.edit_text(not_found_text); return
        
    total_pages = math.ceil(len(target_users) / USERS_PER_PAGE)
    start_index = (page - 1) * USERS_PER_PAGE
    page_users = target_users[start_index : start_index + USERS_PER_PAGE]
    
    keyboard = build_users_keyboard(page_users, page, total_pages, list_type)
    await message.edit_text(f"{title_text} (صفحه {page})", reply_markup=keyboard)

@admin_only
async def list_all_users_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _list_users_base(update, context, list_type='all')

@admin_only
async def list_warning_users_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _list_users_base(update, context, list_type='warning')

async def update_user_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_') # e.g., show_users_page_all_2
    list_type = parts[-2]
    new_page = int(parts[-1])
    await _list_users_base(update, context, list_type=list_type, page=new_page)

async def show_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_') # e.g., user_details_USERNAME_all_1
    username, list_type, page_number = parts[2], parts[3], int(parts[4])
    
    await query.edit_message_text(f"در حال دریافت جزئیات برای `{username}`...", parse_mode=ParseMode.MARKDOWN)
    user_info = await get_user_data(username)
    if not user_info:
        await query.edit_message_text("❌ خطا: کاربر یافت نشد."); return
        
    online_status = "🔘 آفلاین"
    if user_info.get('online_at'):
        try:
            online_at_dt = datetime.datetime.fromisoformat(user_info['online_at'].replace("Z", "+00:00"))
            if (datetime.datetime.now(datetime.timezone.utc) - online_at_dt).total_seconds() < 180:
                online_status = "⚡️ آنلاین"
        except (ValueError, TypeError): pass
        
    used_gb = (user_info.get('used_traffic', 0)) / GB_IN_BYTES
    limit_gb = (user_info.get('data_limit', 0)) / GB_IN_BYTES
    usage_str = f"{used_gb:.2f} GB / " + (f"{limit_gb:.0f} GB" if limit_gb > 0 else "نامحدود")
    
    expire_str = "نامحدود"
    if user_info.get('expire'):
        expire_dt = datetime.datetime.fromtimestamp(user_info['expire'])
        if expire_dt > datetime.datetime.now():
            jalali_date = jdatetime.datetime.fromgregorian(datetime=expire_dt)
            days_left = (expire_dt - datetime.datetime.now()).days
            expire_str = f"{jalali_date.strftime('%Y/%m/%d')} ({days_left} روز مانده)"
        else:
            expire_str = "منقضی شده"
            
    message_text = (
        f"**جزئیات کاربر: `{username}`**\n\n"
        f"▫️ **وضعیت:** {online_status}\n"
        f"▫️ **حجم:** {usage_str}\n"
        f"▫️ **انقضا:** `{expire_str}`"
    )
    
    # --- START OF CHANGE: Added a new button and reorganized the layout ---
    keyboard_rows = [
        [
            InlineKeyboardButton("🔄 تمدید هوشمند", callback_data=f"renew_{username}"),
            InlineKeyboardButton("🧾 ارسال صورتحساب", callback_data=f"send_invoice_{username}")
        ],
        [
            InlineKeyboardButton("➕ افزایش حجم", callback_data=f"add_data_{username}"),
            InlineKeyboardButton("🗓️ افزودن روز", callback_data=f"add_days_{username}")
        ],
        [
            InlineKeyboardButton("♻️ ریست ترافیک", callback_data=f"reset_traffic_{username}"),
            InlineKeyboardButton("📝 اطلاعات اشتراک", callback_data=f"note_{username}")
        ],
        [
            InlineKeyboardButton("🔗 لینک اشتراک", callback_data=f"sub_link_{username}"),
            InlineKeyboardButton("🗑 حذف کاربر", callback_data=f"delete_{username}")
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به لیست", callback_data=f"show_users_page_{list_type}_{page_number}")
        ]
    ]
    # --- END OF CHANGE ---
    await query.edit_message_text(message_text, reply_markup=InlineKeyboardMarkup(keyboard_rows), parse_mode=ParseMode.MARKDOWN)
async def close_pagination_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="به بخش مدیریت کاربران بازگشتید.",
        reply_markup=get_user_management_keyboard()
    )

async def handle_deep_link_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pass