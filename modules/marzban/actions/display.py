# FILE: modules/marzban/actions/display.py (نسخه نهایی با لیست کاربران زیبا و تراز شده)

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
from .constants import USERS_PER_PAGE, GB_IN_BYTES
from .api import get_all_users, get_user_data
from modules.general.actions import start as show_main_menu_action
from modules.auth import admin_only

LOGGER = logging.getLogger(__name__)

# --- توابع جدید و بازنویسی شده برای ظاهر جدید ---

def _pad_string(input_str: str, max_len: int) -> str:
    """فاصله به انتهای رشته اضافه می‌کند تا طول ثابتی داشته باشد."""
    return input_str + ' ' * (max_len - len(input_str))

def get_user_display_info(user: dict) -> tuple[str, str, bool, str, str]:
    """اطلاعات کاربر را برای نمایش پردازش می‌کند."""
    username = user.get('username', 'N/A')
    sanitized_username = username.replace('`', '') # حذف کاراکترهای مخرب
    
    status = user.get('status', 'disabled')
    used_traffic = user.get('used_traffic') or 0
    data_limit = user.get('data_limit') or 0
    expire_timestamp = user.get('expire')
    online_at = user.get('online_at')

    prefix = "🟢"  # پیش‌فرض: فعال
    is_online = False
    days_left_str = "∞"
    data_left_str = "∞"

    # ۱. بررسی وضعیت آنلاین بودن
    if online_at:
        try:
            online_at_dt = datetime.datetime.fromisoformat(online_at.replace("Z", "+00:00"))
            if (datetime.datetime.now(datetime.timezone.utc) - online_at_dt).total_seconds() < 180:
                is_online = True
                prefix = "✨" # ایموجی برای آنلاین
        except (ValueError, TypeError):
            pass

    # ۲. بررسی وضعیت‌های دیگر (قرمز بالاترین اولویت را دارد)
    if status != 'active' or (expire_timestamp and datetime.datetime.fromtimestamp(expire_timestamp) < datetime.datetime.now()):
        prefix = "🔴"
        days_left_str = "Expired"
    else: # اگر قرمز نبود، وضعیت هشدار (زرد) را بررسی کن
        is_warning = False
        if expire_timestamp:
            time_left = datetime.datetime.fromtimestamp(expire_timestamp) - datetime.datetime.now()
            days_left_val = time_left.days + (1 if time_left.seconds > 0 else 0)
            days_left_str = f"{days_left_val} Days"
            if 0 < days_left_val <= 3:
                is_warning = True
        
        if data_limit > 0:
            data_left_gb = (data_limit - used_traffic) / GB_IN_BYTES
            data_left_str = f"{data_left_gb:.1f} GB"
            if data_left_gb < 1:
                is_warning = True
        
        if is_warning:
            prefix = "🟡"
            
    return prefix, sanitized_username, is_online, days_left_str, data_left_str

def build_users_keyboard(users: list, current_page: int, total_pages: int, list_type: str) -> InlineKeyboardMarkup:
    """دکمه‌های تراز شده و زیبا را برای لیست کاربران می‌سازد."""
    keyboard = []
    
    display_data = [get_user_display_info(u) for u in users]
    
    # پیدا کردن طولانی‌ترین نام برای تراز کردن
    max_len = 0
    if display_data:
        # 2 کاراکتر برای ایموجی و فاصله در نظر می‌گیریم
        max_len = max(len(prefix + " " + username) for prefix, username, _, _, _ in display_data)

    for i, user_data in enumerate(display_data):
        prefix, username, is_online, days_left, data_left = user_data
        
        # بخش اول دکمه (نام)
        part1 = _pad_string(f"{prefix} {username}", max_len)
        
        # بخش دوم دکمه (جزئیات)
        if is_online:
            details_part = f"Online  | 📶 {data_left}"
        else:
            details_part = f"⏳ {days_left} | 📶 {data_left}"
        
        full_button_text = f"`{part1}  {details_part}`"
        
        keyboard.append([
            InlineKeyboardButton(
                full_button_text,
                callback_data=f"user_details_{users[i].get('username')}_{list_type}_{current_page}"
            )
        ])
    
    # دکمه‌های ناوبری
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

# --- توابع اصلی که از توابع بالا استفاده می‌کنند ---

@admin_only
async def show_user_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("بخش مدیریت کاربران:", reply_markup=get_user_management_keyboard())

async def _list_users_base(update: Update, context: ContextTypes.DEFAULT_TYPE, list_type: str, page: int = 1):
    is_callback = update.callback_query is not None
    message = update.callback_query.message if is_callback else await update.message.reply_text("در حال بارگذاری...")
    
    if list_type != 'search':
        context.user_data.pop('last_search_results', None)
    
    if is_callback:
        await update.callback_query.answer()
    else:
        await message.edit_text("در حال دریافت و تحلیل لیست کاربران...")
    
    target_users = []
    
    if list_type == 'search':
        title_text = "🔎 نتایج جستجو:"
        not_found_text = "هیچ نتیجه‌ای در جستجوی اخیر یافت نشد."
        target_users = context.user_data.get('last_search_results', [])
    else:
        title_text = "⌛️ کاربران رو به اتمام:" if list_type == 'warning' else "👥 لیست کامل کاربران:"
        not_found_text = "✅ هیچ کاربر نیازمند توجهی یافت نشد." if list_type == 'warning' else "هیچ کاربری در پنل یافت نشد."
        
        all_users = await get_all_users()
        if all_users is None:
            await message.edit_text("❌ خطا در ارتباط با سرور مرزبان."); return
        
        if list_type == 'warning':
            warning_users = []
            for u in all_users:
                prefix, _, is_online, _, _ = get_user_display_info(u)
                if not is_online and prefix in ["🟡", "🔴"]:
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
    
    try:
        keyboard = build_users_keyboard(page_users, page, total_pages, list_type)
        # استفاده از escape_markdown برای امن کردن عنوان
        safe_title = escape_markdown(f"{title_text} (صفحه {page})", version=2)
        await message.edit_text(
            safe_title, 
            reply_markup=keyboard, 
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        LOGGER.error(f"Error building or sending user list keyboard: {e}", exc_info=True)
        await message.edit_text("❌ خطایی در نمایش لیست کاربران رخ داد. لطفاً لاگ‌ها را بررسی کنید.")

@admin_only
async def list_all_users_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _list_users_base(update, context, list_type='all')

@admin_only
async def list_warning_users_paginated(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _list_users_base(update, context, list_type='warning')

async def update_user_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    list_type = parts[-2]
    new_page = int(parts[-1])
    await _list_users_base(update, context, list_type=list_type, page=new_page)

async def show_user_details_panel(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    username: str,
    list_type: str,
    page_number: int,
    success_message: str = None
) -> None:
    user_info = await get_user_data(username)
    if not user_info:
        await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ خطا: کاربر یافت نشد.")
        return
        
    online_status = "🔘 آفلاین"
    if user_info.get('online_at'):
        try:
            online_at_dt = datetime.datetime.fromisoformat(user_info['online_at'].replace("Z", "+00:00"))
            if (datetime.datetime.now(datetime.timezone.utc) - online_at_dt).total_seconds() < 180:
                online_status = "⚡️ آنلاین"
        except (ValueError, TypeError): pass
        
    used_gb = (user_info.get('used_traffic') or 0) / GB_IN_BYTES
    limit_gb = (user_info.get('data_limit') or 0) / GB_IN_BYTES
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
            
    message_text = ""
    if success_message:
        message_text += f"{success_message}\n{'-'*20}\n"
    
    message_text += (
        f"**جزئیات کاربر: `{username}`**\n\n"
        f"▫️ **وضعیت:** {online_status}\n"
        f"▫️ **حجم:** {usage_str}\n"
        f"▫️ **انقضا:** `{expire_str}`"
    )
    
    back_button_callback = f"list_subs_page_{page_number}" if list_type == 'subs' else f"show_users_page_{list_type}_{page_number}"
    back_button_text = "🔙 بازگشت به لیست اشتراک‌ها" if list_type == 'subs' else "🔙 بازگشت به لیست کاربران"
    
    keyboard_rows = [
        [InlineKeyboardButton("🔄 تمدید هوشمند", callback_data=f"renew_{username}"), InlineKeyboardButton("🧾 ارسال صورتحساب", callback_data=f"send_invoice_{username}")],
        [InlineKeyboardButton("➕ افزایش حجم", callback_data=f"add_data_{username}"), InlineKeyboardButton("🗓️ افزودن روز", callback_data=f"add_days_{username}")],
        [InlineKeyboardButton("♻️ ریست ترافیک", callback_data=f"reset_traffic_{username}"), InlineKeyboardButton("📝 اطلاعات اشتراک", callback_data=f"note_{username}")],
        [InlineKeyboardButton("🔗 لینک اشتراک", callback_data=f"sub_link_{username}"), InlineKeyboardButton("🗑 حذف کاربر", callback_data=f"delete_{username}")],
        [InlineKeyboardButton(back_button_text, callback_data=back_button_callback)]
    ]
    
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard_rows),
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        LOGGER.error(f"Failed to edit user details panel for {username}: {e}")

async def show_user_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    username, list_type, page_number = parts[2], parts[3], int(parts[4])
    
    context.user_data['current_list_type'] = list_type
    context.user_data['current_page'] = page_number
    
    await query.edit_message_text(f"در حال دریافت جزئیات برای `{username}`...", parse_mode=ParseMode.MARKDOWN)
    
    await show_user_details_panel(
        context=context,
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        username=username,
        list_type=list_type,
        page_number=page_number
    )
    
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
    # ======================== START: FIX for duplicate panel ========================
    now = time.time()
    last_call = context.user_data.get('last_deeplink_call', 0)
    if now - last_call < 2:  # 2 seconds cooldown
        return  # Ignore rapid-fire calls
    context.user_data['last_deeplink_call'] = now
    # ========================= END: FIX for duplicate panel =========================

    user = update.effective_user
    if user.id not in config.AUTHORIZED_USER_IDS:
        await show_main_menu_action(update, context)
        return

    try:
        if not context.args or not context.args[0].startswith('details_'):
            await show_main_menu_action(update, context)
            return
        username = context.args[0].split('_', 1)[1]
    except (IndexError, AttributeError):
        await update.message.reply_text("لینک نامعتبر است.")
        await show_main_menu_action(update, context)
        return

    loading_msg = await update.message.reply_text(f"در حال دریافت جزئیات برای `{username}`...", parse_mode=ParseMode.MARKDOWN)
    
    await show_user_details_panel(
        context=context,
        chat_id=loading_msg.chat_id,
        message_id=loading_msg.message_id,
        username=username,
        list_type='all',
        page_number=1
    )