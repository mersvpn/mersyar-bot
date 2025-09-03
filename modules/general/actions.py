# FILE: modules/general/actions.py (نسخه نهایی با تابع کمکی مرکزی)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from database import db_manager
from shared.log_channel import send_log
from telegram.helpers import escape_markdown
from config import config
from shared.keyboards import (
    get_customer_main_menu_keyboard,
    get_admin_main_menu_keyboard,
    get_customer_view_for_admin_keyboard
)
from modules.marzban.actions.data_manager import link_user_to_telegram, normalize_username
from modules.auth import admin_only

LOGGER = logging.getLogger(__name__)

# =============================================================================
#  تابع کمکی جدید و مرکزی برای نمایش منوی اصلی
# =============================================================================

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text: str = "") -> None:
    """
    A central helper function to send the correct main menu to the user.
    It checks if the user is an admin, and if so, whether they are in customer view.
    """
    user = update.effective_user
    
    # Default welcome message if none is provided
    if not message_text:
        message_text = f"سلام {user.first_name} عزیز!\nبه ربات ما خوش آمدید."

    if user.id in config.AUTHORIZED_USER_IDS:
        if context.user_data.get('is_admin_in_customer_view'):
            reply_markup = get_customer_view_for_admin_keyboard()
            message_text += "\n\nشما در حال مشاهده پنل به عنوان یک کاربر هستید."
        else:
            reply_markup = get_admin_main_menu_keyboard()
            message_text += "\n\nداشبورد مدیریتی برای شما فعال است."
    else:
        reply_markup = get_customer_main_menu_keyboard()
        message_text += "\n\nبرای شروع، می‌توانید از دکمه‌های زیر استفاده کنید."

    # Determine how to send the message (reply or new message)
    if update.callback_query:
        # If triggered by a callback, it's cleaner to delete the old message
        try:
            await update.callback_query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(chat_id=user.id, text=message_text, reply_markup=reply_markup)
    elif update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        # Fallback for cases where 'update' has no message/callback (e.g., called from a job)
        await context.bot.send_message(chat_id=user.id, text=message_text, reply_markup=reply_markup)


# =============================================================================
#  توابع اصلی
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    user = update.effective_user
    is_new_user = False
    try:
        is_new_user = await db_manager.add_or_update_user(user)
        
        if is_new_user:
            LOGGER.info(f"A new user has started the bot: {user.id} ({user.first_name})")
            safe_full_name = escape_markdown(user.full_name, version=2)
            user_info_markdown = f"کاربر {safe_full_name} \(ID: `{user.id}`\)"
            if user.username:
                safe_username = escape_markdown(user.username, version=2)
                user_info_markdown += f" \(@{safe_username}\)"
            
            log_message = f"👤 *کاربر جدید*\n{user_info_markdown} ربات را استارت زد\."
            await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN_V2)

            user_info_pv = (
                f"👤 **کاربر جدید ربات را استارت زد**\n\n"
                f"**نام:** {user.first_name}\n"
                f"**آیدی عددی:** `{user.id}`"
            )
            if user.username:
                user_info_pv += f"\n**نام کاربری:** @{user.username}"
            
            for admin_id in config.AUTHORIZED_USER_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id, text=user_info_pv, parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    LOGGER.error(f"Failed to send new user notification to admin {admin_id}: {e}")

    except Exception as e:
        LOGGER.error(f"Failed to save user {user.id} to the database: {e}", exc_info=True)

    # Now, simply call the central function to send the appropriate menu
    await send_main_menu(update, context)


@admin_only
async def switch_to_customer_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switches the admin's view to the customer panel."""
    context.user_data['is_admin_in_customer_view'] = True
    await update.message.reply_text(
        "✅ شما اکنون در **نمای کاربری** هستید.",
        reply_markup=get_customer_view_for_admin_keyboard(), parse_mode=ParseMode.MARKDOWN
    )

@admin_only
async def switch_to_admin_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switches the admin's view back to the admin panel."""
    if 'is_admin_in_customer_view' in context.user_data:
        del context.user_data['is_admin_in_customer_view']
    await update.message.reply_text(
        "✅ شما به **پنل ادمین** بازگشتید.",
        reply_markup=get_admin_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN
    )
    

async def handle_user_linking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from modules.marzban.actions.api import get_user_data
    from database.db_manager import add_user_to_managed_list
    user = update.effective_user
    try:
        marzban_username_raw = context.args[0].split('-', 1)[1]
    except (IndexError, AttributeError):
        await update.message.reply_text("لینک اتصال نامعتبر است.")
        await start(update, context)
        return
    normalized_username = normalize_username(marzban_username_raw)
    loading_msg = await update.message.reply_text(f"در حال اتصال سرویس `{marzban_username_raw}`...")
    marzban_user_data = await get_user_data(normalized_username)
    if not marzban_user_data or "error" in marzban_user_data:
        await loading_msg.edit_text(f"❌ **خطا:** سرویسی با نام `{marzban_username_raw}` در پنل یافت نشد.")
        return
    existing_link = await db_manager.get_telegram_id_from_marzban_username(normalized_username)
    if existing_link and existing_link != user.id:
        await loading_msg.edit_text("❌ **خطا:** این سرویس قبلاً به حساب تلگرام دیگری متصل شده است.")
        return
    success_link = await link_user_to_telegram(normalized_username, user.id)
    if not success_link:
        await loading_msg.edit_text("❌ **خطای پایگاه داده:** لطفاً با پشتیبانی تماس بگیرید.")
        return
    await add_user_to_managed_list(normalized_username)
    await loading_msg.edit_text(f"✅ حساب شما با موفقیت به سرویس `{normalized_username}` متصل شد!")
    admin_message = f"✅ **اتصال موفق:** کاربر `{normalized_username}` به {user.mention_markdown_v2()} متصل شد\."
    for admin_id in config.AUTHORIZED_USER_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            LOGGER.error(f"Failed to send linking notification to admin {admin_id}: {e}")
    await start(update, context)

# (توابع دیگر مانند show_my_id و get_maintenance_message بدون تغییر باقی می‌مانند)
# ...
async def show_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your Telegram User ID is:\n`{user_id}`", parse_mode=ParseMode.MARKDOWN)

async def get_maintenance_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message_text = (
        "🛠 **ربات در حال تعمیر و به‌روزرسانی است** 🛠\n\n"
        "در حال حاضر امکان پاسخگویی وجود ندارد. لطفاً کمی بعد دوباره تلاش کنید.\n\n"
        "از شکیبایی شما سپاسگزاریم."
    )
    if update.message:
        await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN)
    elif update.callback_query:
        await update.callback_query.answer(message_text, show_alert=True)