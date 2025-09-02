# FILE: modules/general/actions.py

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
# Import the helper function for two-column layout


LOGGER = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    welcome_message = f"سلام {user.first_name} عزیز!\nبه ربات ما خوش آمدید."
    if user.id in config.AUTHORIZED_USER_IDS:
        reply_markup = get_admin_main_menu_keyboard()
        welcome_message += "\n\nداشبورد مدیریتی برای شما فعال است."
    else:
        reply_markup = get_customer_main_menu_keyboard()
        welcome_message += "\n\nبرای شروع، می‌توانید از دکمه‌های زیر استفاده کنید."

    if update.callback_query:
        try:
            await update.callback_query.message.delete()
        except Exception: pass
        await context.bot.send_message(chat_id=user.id, text=welcome_message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)


async def handle_guide_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays a menu of available guide sections to the user."""
    sections = await db_manager.get_all_guide_sections()
    
    if not sections:
        await update.message.reply_text("در حال حاضر هیچ راهنمایی تنظیم نشده است.")
        return

    buttons = [
        InlineKeyboardButton(section['title'], callback_data=f"show_guide_{section['id']}")
        for section in sections
    ]
    
    # Use the helper to create a two-column layout
    keyboard_layout = build_two_column_keyboard(buttons)
    
    await update.message.reply_text(
        "📚 لطفاً یکی از راهنماهای زیر را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard_layout)
    )

async def show_guide_section(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the content of a selected guide section."""
    query = update.callback_query
    await query.answer()

    try:
        section_id = int(query.data.split('_')[-1])
    except (ValueError, IndexError):
        await query.edit_message_text("خطا: راهنمای نامعتبر.")
        return

    section = await db_manager.get_guide_section_by_id(section_id)
    if not section:
        await query.edit_message_text("خطا: این راهنما یافت نشد یا حذف شده است.")
        return

    # Delete the menu message for a cleaner UI
    await query.message.delete()

    photo_id = section.get('photo_id')
    text = section.get('text') or "محتوایی برای این بخش تنظیم نشده است."
    buttons = section.get('buttons', [])

    keyboard = []
    if buttons:
        for button_data in buttons:
            keyboard.append([InlineKeyboardButton(button_data['text'], url=button_data['url'])])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    if photo_id:
        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=photo_id,
            caption=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    else:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

# ... (سایر توابع)
async def show_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your Telegram User ID is:\n`{user_id}`", parse_mode=ParseMode.MARKDOWN)

@admin_only
async def switch_to_customer_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "✅ شما اکنون در **نمای کاربری** هستید.",
        reply_markup=get_customer_view_for_admin_keyboard(), parse_mode=ParseMode.MARKDOWN
    )

@admin_only
async def switch_to_admin_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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