# FILE: modules/customer/actions/service.py

import datetime
import jdatetime
import logging
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from shared.keyboards import get_customer_main_menu_keyboard
# <--- اصلاح شد: این import دیگر لازم نیست و حذف می‌شود
# from modules.marzban.actions.data_manager import load_users_map, normalize_username
# --->
from modules.marzban.actions.api import get_user_data, reset_subscription_url_api, get_all_users
from modules.marzban.actions.constants import GB_IN_BYTES
from modules.marzban.actions.data_manager import normalize_username
# <--- اصلاح شد: تابع جدید از دیتابیس وارد می‌شود
from database.db_manager import get_linked_marzban_usernames
# --->


LOGGER = logging.getLogger(__name__)

CHOOSE_SERVICE, DISPLAY_SERVICE, CONFIRM_RESET_SUB, CONFIRM_DELETE = range(4)

async def display_service_details(update: Update, context: ContextTypes.DEFAULT_TYPE, marzban_username: str) -> int:
    from database.db_manager import get_user_note_and_duration

    target_message = update.callback_query.message if update.callback_query else update.message
    
    await context.bot.edit_message_text(
        chat_id=target_message.chat_id,
        message_id=target_message.message_id,
        text=f"در حال دریافت اطلاعات سرویس «{marzban_username}»..."
    )

    user_info = await get_user_data(marzban_username)
    if not user_info or "error" in user_info:
        await target_message.edit_text("❌ خطا: این سرویس در پنل یافت نشد یا غیرفعال است.")
        return ConversationHandler.END

    usage_gb = (user_info.get('used_traffic') or 0) / GB_IN_BYTES
    limit_gb = (user_info.get('data_limit') or 0) / GB_IN_BYTES
    usage_str = f"{usage_gb:.2f} GB" + (f" / {limit_gb:.0f} GB" if limit_gb > 0 else " (از نامحدود)")

    expire_str = "نامحدود"
    duration_str = "نامشخص"

    note_data = await get_user_note_and_duration(normalize_username(marzban_username))
    if note_data and note_data.get('subscription_duration'):
        duration_str = f"{note_data['subscription_duration']} روزه"

    if user_info.get('expire'):
        expire_date = datetime.datetime.fromtimestamp(user_info['expire'])
        if (expire_date - datetime.datetime.now()).total_seconds() > 0:
            jalali_date = jdatetime.datetime.fromgregorian(datetime=expire_date)
            time_left = expire_date - datetime.datetime.now()
            expire_str = f"{jalali_date.strftime('%Y/%m/%d')} ({time_left.days} روز باقی‌مانده)"
        else:
            expire_str = "منقضی شده"

    sub_url = user_info.get('subscription_url', 'یافت نشد')
    message = (
        f"📊 **مشخصات سرویس**\n\n"
        f"▫️ **نام کاربری:** `{marzban_username}`\n"
        f"▫️ **حجم:** {usage_str}\n"
        f"▫️ **طول دوره:** {duration_str}\n"
        f"▫️ **انقضا:** `{expire_str}`\n\n"
        f"🔗 **لینک اشتراک:**\n`{sub_url}`"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 درخواست تمدید", callback_data=f"customer_renew_request_{marzban_username}")],
        [
            InlineKeyboardButton("🔗 بازسازی لینک", callback_data=f"customer_reset_sub_{marzban_username}"),
            InlineKeyboardButton("🗑 درخواست حذف", callback_data=f"request_delete_{marzban_username}")
        ],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="customer_back_to_main_menu")]
    ])
    
    await target_message.edit_text(message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return DISPLAY_SERVICE
    
async def handle_my_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    loading_message = await update.message.reply_text("در حال بررسی سرویس‌های شما از طریق دیتابیس...")

    # <--- اصلاح شد: این بلاک کد به طور کامل با فراخوانی از دیتابیس جایگزین می‌شود
    # users_map = await load_users_map()
    # linked_accounts_usernames = [
    #     username for username, t_id in users_map.items() if t_id == user_id
    # ]
    linked_accounts_usernames = await get_linked_marzban_usernames(user_id)
    # --->
    
    LOGGER.info(f"DEBUG (handle_my_service): User {user_id} is linked to these accounts in DATABASE: {linked_accounts_usernames}")

    if not linked_accounts_usernames:
        await loading_message.edit_text("سرویس فعالی برای شما یافت نشد.")
        return ConversationHandler.END

    all_marzban_users_list = await get_all_users()
    if all_marzban_users_list is None:
        await loading_message.edit_text("❌ خطا در ارتباط با پنل. لطفاً بعداً تلاش کنید.")
        return ConversationHandler.END
        
    all_marzban_users_dict = {
        normalize_username(user['username']): user 
        for user in all_marzban_users_list
    }
    
    # <--- اصلاح شد: نام متغیر برای خوانایی بهتر تغییر کرد
    normalized_linked_usernames = [normalize_username(u) for u in linked_accounts_usernames]
    
    active_linked_accounts = [
        all_marzban_users_dict[normalized_username] 
        for normalized_username in normalized_linked_usernames # <--- از متغیر جدید استفاده شد
        if normalized_username in all_marzban_users_dict and all_marzban_users_dict[normalized_username].get('status') == 'active'
    ]
    # --->
    
    active_usernames_for_log = [acc['username'] for acc in active_linked_accounts]
    LOGGER.info(f"DEBUG (handle_my_service): Found {len(active_linked_accounts)} active accounts in Marzban panel: {active_usernames_for_log}")

    if not active_linked_accounts:
        await loading_message.edit_text("هیچ سرویس فعالی در پنل برای شما یافت نشد.")
        return ConversationHandler.END

    if len(active_linked_accounts) == 1:
        class DummyQuery:
            def __init__(self, message): self.message = message
        dummy_update = type('obj', (object,), {'callback_query': DummyQuery(loading_message)})
        original_username = active_linked_accounts[0]['username']
        return await display_service_details(dummy_update, context, original_username)

    keyboard = [
        [InlineKeyboardButton(f"سرویس: {user['username']}", callback_data=f"select_service_{user['username']}")] 
        for user in sorted(active_linked_accounts, key=lambda u: u['username'].lower())
    ]
    keyboard.append([InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="customer_back_to_main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await loading_message.edit_text("شما چندین سرویس فعال دارید. لطفاً یکی را انتخاب کنید:", reply_markup=reply_markup)
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
    text = "⚠️ **اخطار** ⚠️\n\nبا بازسازی لینک، **لینک قبلی از کار خواهد افتاد**.\n\nآیا مطمئن هستید؟"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، بازسازی کن", callback_data=f"do_reset_sub_{username}")],
        [InlineKeyboardButton("❌ خیر، بازگرد", callback_data=f"select_service_{username}")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_RESET_SUB

async def execute_reset_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    if not username:
        await query.edit_message_text("خطا: نام کاربری یافت نشد.")
        return ConversationHandler.END

    await query.edit_message_text(f"در حال بازسازی لینک برای `{username}`...")
    success, result = await reset_subscription_url_api(username)

    if success:
        new_sub_url = result.get('subscription_url', 'خطا در دریافت لینک')
        text = f"✅ لینک بازسازی شد:\n\n`{new_sub_url}`"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به جزئیات", callback_data=f"select_service_{username}")]])
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        await query.edit_message_text(f"❌ خطا در بازسازی: {result}")
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت به جزئیات", callback_data=f"select_service_{username}")]])
        await query.message.reply_text("لطفا مجددا تلاش کنید یا با پشتیبانی تماس بگیرید", reply_markup=keyboard)
    return DISPLAY_SERVICE

async def back_to_main_menu_customer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="به منوی اصلی بازگشتید.",
        reply_markup=get_customer_main_menu_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def request_delete_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    text = (
        f"⚠️ **اخطار: این عمل غیرقابل بازگشت است.** ⚠️\n\n"
        f"آیا از درخواست حذف کامل سرویس `{username}` اطمینان دارید؟"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ بله، درخواست حذف ارسال شود", callback_data=f"confirm_delete_{username}")],
        [InlineKeyboardButton("❌ خیر، منصرف شدم", callback_data=f"select_service_{username}")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_DELETE

async def confirm_delete_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from config import config
    query = update.callback_query
    await query.answer()
    username = query.data.split('_')[-1]
    user = update.effective_user
    await query.edit_message_text(
        "✅ درخواست شما برای حذف سرویس با موفقیت برای ادمین ارسال شد.\n"
        "لطفاً منتظر بمانید."
    )
    if config.AUTHORIZED_USER_IDS:
        user_info = f"کاربر {user.full_name}"
        if user.username:
            user_info += f" (@{user.username})"
        user_info += f"\nUser ID: `{user.id}`"
        message_to_admin = (
            f"🗑️ **درخواست حذف سرویس** 🗑️\n\n"
            f"{user_info}\n"
            f"نام کاربری در پنل: `{username}`\n\n"
            "این کاربر درخواست حذف کامل این سرویس را دارد."
        )
        admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ تایید حذف", callback_data=f"admin_confirm_delete_{username}_{user.id}")],
            [InlineKeyboardButton("❌ رد درخواست", callback_data=f"admin_reject_delete_{username}_{user.id}")]
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