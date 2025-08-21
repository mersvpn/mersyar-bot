# (کد کامل فایل display.py برای جایگزینی آسان)
# ===== IMPORTS & DEPENDENCIES =====
import math
import datetime
import jdatetime
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# --- Local Imports ---
from shared.keyboards import get_user_management_keyboard
from .constants import USERS_PER_PAGE, GB_IN_BYTES
from .api import get_all_users, get_user_data
from modules.general.actions import start as show_main_menu_action
from modules.auth import admin_only

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# ===== DISPLAY LOGIC (INTERNAL HELPERS) =====

def get_user_display_info(user: dict) -> tuple[str, str]:
    username = user.get('username', 'N/A')
    status = user.get('status', 'disabled')
    used_traffic = user.get('used_traffic') or 0
    data_limit = user.get('data_limit') or 0
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
            if 0 < time_left.days < 3:
                emojis.append("⏳")
                issues.append(f"{time_left.days+1} روز مانده")
        if data_limit > 0 and (data_limit - used_traffic) < (1 * GB_IN_BYTES):
            if "⏳" not in emojis: emojis.append("📉")
            issues.append("حجم کم")
    if not emojis:
        emojis.append("✅")
    formatted_name = "".join(sorted(list(set(emojis)))) + f" {username}"
    details_text = ", ".join(issues) if issues else "فعال"
    return formatted_name, details_text

def build_users_keyboard(users: list, current_page: int, list_type: str) -> InlineKeyboardMarkup:
    users.sort(key=lambda u: (u.get('username', '') or '').lower())
    total_pages = math.ceil(len(users) / USERS_PER_PAGE)
    keyboard, start_index = [], (current_page - 1) * USERS_PER_PAGE
    page_users = users[start_index : start_index + USERS_PER_PAGE]
    for i in range(0, len(page_users), 2):
        row = []
        user1 = page_users[i]
        formatted_name1, _ = get_user_display_info(user1)
        row.append(InlineKeyboardButton(formatted_name1, callback_data=f"user_details_{user1.get('username', '')}"))
        if i + 1 < len(page_users):
            user2 = page_users[i+1]
            formatted_name2, _ = get_user_display_info(user2)
            row.append(InlineKeyboardButton(formatted_name2, callback_data=f"user_details_{user2.get('username', '')}"))
        keyboard.append(row)
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"page_{list_type}_{current_page - 1}"))
    if total_pages > 0:
        nav_row.append(InlineKeyboardButton(f"صفحه {current_page}/{total_pages}", callback_data="noop"))
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"page_{list_type}_{current_page + 1}"))
    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([InlineKeyboardButton("✖️ بستن", callback_data="close_pagination")])
    return InlineKeyboardMarkup(keyboard)

# ===== ACTION FUNCTIONS (PUBLIC HANDLERS) =====

@admin_only
async def show_user_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("بخش مدیریت کاربران:", reply_markup=get_user_management_keyboard())

async def _list_users_base(update: Update, context: ContextTypes.DEFAULT_TYPE, list_type: str):
    if list_type == 'warning':
        loading_text, title_text, not_found_text = "در حال یافتن کاربران نیازمند توجه...", "کاربران نیازمند توجه:", "هیچ کاربر نیازمند توجهی یافت نشد. ✅"
    else:
        loading_text, title_text, not_found_text = "در حال دریافت و تحلیل لیست کامل کاربران...", "لیست کامل کاربران:", "هیچ کاربری در پنل یافت نشد."
    message_to_edit = await update.message.reply_text(loading_text)
    all_users = await get_all_users()
    if all_users is None:
        await message_to_edit.edit_text("❌ خطا در ارتباط با سرور مرزبان."); return
    if not all_users:
        await message_to_edit.edit_text(not_found_text); return
    target_users = [user for user in all_users if "✅" not in get_user_display_info(user)[0]] if list_type == 'warning' else all_users
    if not target_users:
        await message_to_edit.edit_text(not_found_text); return
    context.bot_data[f'user_list_{list_type}'] = target_users
    context.user_data['current_page'] = 1
    keyboard = build_users_keyboard(target_users, current_page=1, list_type=list_type)
    await message_to_edit.edit_text(title_text, reply_markup=keyboard)

@admin_only
async def list_all_users_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _list_users_base(update, context, 'all')

@admin_only
async def list_warning_users_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _list_users_base(update, context, 'warning')

async def update_user_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, list_type, new_page_str = query.data.split('_')
    new_page = int(new_page_str)
    user_list = context.bot_data.get(f'user_list_{list_type}')
    if not user_list:
        await query.edit_message_text("خطا: لیست کاربران منقضی شده است. لطفاً دوباره لیست را از منو باز کنید."); return
    context.user_data['current_page'] = new_page
    keyboard = build_users_keyboard(user_list, new_page, list_type)
    await query.edit_message_text(f"لیست کاربران (صفحه {new_page}):", reply_markup=keyboard)

async def show_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    username_to_find = query.data.split('_', 2)[-1]
    await query.edit_message_text(f"در حال دریافت جزئیات برای «{username_to_find}»...")
    user_info = await get_user_data(username_to_find)
    if not user_info:
        await query.edit_message_text("خطا: کاربر یافت نشد یا اطلاعات او قابل دریافت نیست."); return
    online_status_text = "🔘 **آفلاین**"
    if user_info.get('online_at'):
        try:
            online_at_dt = datetime.datetime.fromisoformat(user_info['online_at'].replace("Z", "+00:00"))
            if (datetime.datetime.now(datetime.timezone.utc) - online_at_dt).total_seconds() < 180:
                online_status_text = "⚡️ **آنلاین**"
        except (ValueError, TypeError): pass
    formatted_name, _ = get_user_display_info(user_info)
    sub_url = user_info.get('subscription_url', 'یافت نشد')
    used_traffic_bytes = user_info.get('used_traffic') or 0
    limit_bytes = user_info.get('data_limit') or 0
    usage_gb = used_traffic_bytes / GB_IN_BYTES
    limit_gb = limit_bytes / GB_IN_BYTES
    usage_str = f"{usage_gb:.2f} GB / " + (f"{limit_gb:.0f} GB" if limit_gb > 0 else "نامحدود")
    expire_str = "نامحدود"
    if user_info.get('expire'):
        expire_date = datetime.datetime.fromtimestamp(user_info['expire'])
        if (expire_date - datetime.datetime.now()).total_seconds() > 0:
            jalali_date = jdatetime.datetime.fromgregorian(datetime=expire_date)
            time_left = expire_date - datetime.datetime.now()
            expire_str = f"{jalali_date.strftime('%Y/%m/%d')} ({time_left.days} روز مانده)"
        else:
            expire_str = "منقضی شده"
    message = (f"**{formatted_name}**\n\n"
               f"▫️ **وضعیت:** {online_status_text}\n"
               f"▫️ **حجم:** {usage_str}\n"
               f"▫️ **انقضا:** `{expire_str}`\n\n"
               f"🔗 **لینک اشتراک:**\n`{sub_url}`")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تمدید", callback_data=f"renew_{username_to_find}"), InlineKeyboardButton("➕ افزایش حجم", callback_data=f"add_data_{username_to_find}")],
        [InlineKeyboardButton("🗓️ افزودن روز", callback_data=f"add_days_{username_to_find}"), InlineKeyboardButton("♻️ ریست ترافیک", callback_data=f"reset_traffic_{username_to_find}")],
        [InlineKeyboardButton("📝 یادداشت", callback_data=f"note_{username_to_find}"), InlineKeyboardButton("🗑 حذف", callback_data=f"delete_{username_to_find}")],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="back_to_main_menu")]
    ])
    await query.edit_message_text(message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

async def close_pagination_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.delete_message()

async def back_to_main_menu_from_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.delete_message()
    await show_main_menu_action(update, context)

async def handle_deep_link_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args: return
    try:
        username = context.args[0].split('_', 1)[1]
    except IndexError:
        return
    class FakeCallbackQuery:
        def __init__(self, message, data):
            self.message = message
            self.data = data
        async def answer(self): pass
        async def edit_message_text(self, *args, **kwargs):
            await self.message.reply_text(*args, **kwargs)
    fake_query = FakeCallbackQuery(update.effective_message, f"user_details_{username}")
    fake_update = Update(update.update_id, callback_query=fake_query)
    await show_user_details(fake_update, context)