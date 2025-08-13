# ===== IMPORTS & DEPENDENCIES =====
import datetime
import jdatetime
import logging
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# --- Local Imports ---
# CORRECTED: Import keyboards from the new shared location
from shared.keyboards import get_customer_main_menu_keyboard
from modules.marzban.actions.data_manager import load_users_map, normalize_username
from modules.marzban.actions.api import get_user_data, reset_subscription_url_api, get_all_users
from modules.marzban.actions.constants import GB_IN_BYTES

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# --- CONSTANTS ---
CHOOSE_SERVICE, DISPLAY_SERVICE, CONFIRM_RESET_SUB, CONFIRM_DELETE = range(4)

# ===== MAIN CONVERSATION LOGIC =====

async def display_service_details(update: Update, context: ContextTypes.DEFAULT_TYPE, marzban_username: str) -> int:
    """Fetches and displays detailed information for a specific service."""
    target_message = update.callback_query.message if update.callback_query else update.message
    normalized_user = normalize_username(marzban_username)

    await context.bot.edit_message_text(
        chat_id=target_message.chat_id,
        message_id=target_message.message_id,
        text=f"در حال دریافت اطلاعات سرویس «{normalized_user}»..."
    )

    user_info = await get_user_data(normalized_user)
    if not user_info:
        await target_message.edit_text("❌ خطا: این سرویس در پنل یافت نشد یا غیرفعال است.")
        return ConversationHandler.END

    usage_gb = (user_info.get('used_traffic') or 0) / GB_IN_BYTES
    limit_gb = (user_info.get('data_limit') or 0) / GB_IN_BYTES
    usage_str = f"{usage_gb:.2f} GB" + (f" / {limit_gb:.0f} GB" if limit_gb > 0 else " (از نامحدود)")

    expire_str = "نامحدود"
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
        f"▫️ **نام کاربری:** `{normalized_user}`\n"
        f"▫️ **حجم:** {usage_str}\n"
        f"▫️ **انقضا:** `{expire_str}`\n\n"
        f"🔗 **لینک اشتراک:**\n`{sub_url}`"
    )

    # --- CORRECTED: Added the missing "Back to Main Menu" button ---
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 بازسازی لینک", callback_data=f"customer_reset_sub_{normalized_user}"),
            InlineKeyboardButton("🗑 درخواست حذف", callback_data=f"request_delete_{normalized_user}")
        ],
        [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="customer_back_to_main_menu")]
    ])
    
    await target_message.edit_text(message, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    return DISPLAY_SERVICE

async def handle_my_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for 'My Service'. Finds all active accounts linked to the user."""
    user_id = update.effective_user.id
    loading_message = await update.message.reply_text("در حال بررسی سرویس‌های شما...")

    users_map = await load_users_map()
    linked_accounts = [username for username, t_id in users_map.items() if t_id == user_id]

    if not linked_accounts:
        await loading_message.edit_text("سرویس فعالی برای شما یافت نشد."); return ConversationHandler.END

    all_marzban_users_list = await get_all_users()
    if all_marzban_users_list is None:
        await loading_message.edit_text("❌ خطا در ارتباط با پنل. لطفاً بعداً تلاش کنید."); return ConversationHandler.END

    active_marzban_usernames = {normalize_username(user['username']) for user in all_marzban_users_list if user.get('status') == 'active'}
    active_linked_accounts = [acc for acc in linked_accounts if acc in active_marzban_usernames]

    if not active_linked_accounts:
        await loading_message.edit_text("هیچ سرویس فعالی در پنل برای شما یافت نشد."); return ConversationHandler.END

    if len(active_linked_accounts) == 1:
        class DummyQuery:
            def __init__(self, message): self.message = message
        dummy_update = type('obj', (object,), {'callback_query': DummyQuery(loading_message)})
        return await display_service_details(dummy_update, context, active_linked_accounts[0])

    # --- CORRECTED: Added a "Cancel" button to the keyboard ---
    keyboard = [[InlineKeyboardButton(f"سرویس: {username}", callback_data=f"select_service_{username}")] for username in sorted(active_linked_accounts)]
    
    # Add the cancel button in its own row at the bottom
    keyboard.append([InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="customer_back_to_main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await loading_message.edit_text("شما چندین سرویس فعال دارید. لطفاً یکی را انتخاب کنید:", reply_markup=reply_markup)
    return CHOOSE_SERVICE

async def choose_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles user's choice from the list of multiple services."""
    query = update.callback_query; await query.answer()
    marzban_username = query.data.split('select_service_')[-1]
    return await display_service_details(update, context, marzban_username)

async def confirm_reset_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks for confirmation before resetting the subscription link."""
    query = update.callback_query; await query.answer()
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
    """Executes the subscription link reset via the API."""
    query = update.callback_query; await query.answer()
    username = query.data.split('_')[-1]
    if not username:
        await query.edit_message_text("خطا: نام کاربری یافت نشد."); return ConversationHandler.END

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
    """Clears user_data and returns to the main menu, deleting the service message."""
    query = update.callback_query; await query.answer()
    await query.message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="به منوی اصلی بازگشتید.",
        reply_markup=get_customer_main_menu_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

# ===== DELETE REQUEST FLOW =====
async def request_delete_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks for confirmation before sending a delete request to admins."""
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
    """Confirms the deletion request and notifies admins."""
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