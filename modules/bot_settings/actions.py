# FILE: modules/bot_settings/actions.py (نسخه نهایی با حذف دکمه زائد)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, error
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode

from shared.keyboards import get_settings_and_tools_keyboard, get_helper_tools_keyboard
from .data_manager import is_bot_active, set_bot_status

LOGGER = logging.getLogger(__name__)

MENU_STATE = 0
SET_CHANNEL_ID = 1

# ==================== توابع منوها ====================
async def show_helper_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🛠️ ابزارهای کمکی:", reply_markup=get_helper_tools_keyboard())

async def back_to_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("به بخش «تنظیمات و ابزارها» بازگشتید.", reply_markup=get_settings_and_tools_keyboard())

# ==================== مکالمه تنظیم کانال ====================
async def prompt_for_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database.db_manager import load_bot_settings
    bot_settings = await load_bot_settings()
    current_channel_id = bot_settings.get('log_channel_id', 'تنظیم نشده')
    await update.message.reply_text(
        f"ID فعلی کانال گزارش: `{current_channel_id}`\n\n"
        "لطفاً ID جدید کانال گزارش را وارد کنید.\n"
        "(ID کانال‌های عمومی با `@` شروع می‌شود و کانال‌های خصوصی با `-100`)\n\n"
        "برای لغو /cancel را ارسال کنید.",
        parse_mode=ParseMode.MARKDOWN
    )
    return SET_CHANNEL_ID

async def process_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database.db_manager import save_bot_settings
    channel_id = update.message.text.strip()
    if not (channel_id.startswith('@') or channel_id.startswith('-100')):
        await update.message.reply_text("❌ ID نامعتبر است. لطفاً یک ID صحیح وارد کنید.")
        return SET_CHANNEL_ID
    await save_bot_settings({'log_channel_id': channel_id})
    await update.message.reply_text(
        f"✅ ID کانال گزارش به `{channel_id}` تغییر یافت.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_settings_and_tools_keyboard()
    )
    return ConversationHandler.END

# ==================== مکالمه تنظیمات ربات ====================
async def _build_and_send_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.db_manager import load_bot_settings
    query = update.callback_query
    
    bot_settings = await load_bot_settings()
    is_active_status = await is_bot_active()
    
    maintenance_btn_text = "✅ روشن" if is_active_status else "❌ خاموش (تعمیرات)"
    maintenance_callback = "toggle_maintenance_disable" if is_active_status else "toggle_maintenance_enable"

    log_channel_is_enabled = bot_settings.get('is_log_channel_enabled', False)
    log_channel_btn_text = "✅ فعال" if log_channel_is_enabled else "❌ غیرفعال"
    log_channel_callback = "toggle_log_channel_disable" if log_channel_is_enabled else "toggle_log_channel_enable"
    
    # --- دکمه حذف خودکار حذف شد ---
    keyboard = [
        [
            InlineKeyboardButton(maintenance_btn_text, callback_data=maintenance_callback),
            InlineKeyboardButton("📡 وضعیت ربات", callback_data="noop")
        ],
        [
            InlineKeyboardButton(log_channel_btn_text, callback_data=log_channel_callback),
            InlineKeyboardButton("📣 کانال گزارش", callback_data="noop")
        ],
        [InlineKeyboardButton("🔙 بازگشت به ابزارها", callback_data="bot_status_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    menu_text = "🔧 **تنظیمات ربات**\n\nوضعیت قابلیت‌های اصلی ربات را با کلیک روی دکمه‌های روشن/خاموش مدیریت کنید."

    target_message = query.message if query else update.message
    if query:
        await query.answer()
        try:
            await query.edit_message_text(menu_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except error.BadRequest as e:
            if "Message is not modified" not in str(e): LOGGER.error(f"Error editing bot settings menu: {e}")
    else:
        if update.message: await update.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=menu_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )

async def start_bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _build_and_send_menu(update, context)
    return MENU_STATE

async def toggle_maintenance_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    new_status_is_active = (query.data == "toggle_maintenance_enable")
    await set_bot_status(new_status_is_active)
    feedback = "ربات فعال و آنلاین شد." if new_status_is_active else "ربات در حالت تعمیرات قرار گرفت."
    await query.answer(feedback, show_alert=True)
    await _build_and_send_menu(update, context)
    return MENU_STATE

async def toggle_log_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database.db_manager import save_bot_settings
    query = update.callback_query
    new_status = (query.data == "toggle_log_channel_enable")
    await save_bot_settings({"is_log_channel_enabled": new_status})
    feedback = "ارسال گزارش به کانال فعال شد." if new_status else "ارسال گزارش به کانال غیرفعال شد."
    await query.answer(feedback, show_alert=True)
    await _build_and_send_menu(update, context)
    return MENU_STATE

async def back_to_tools(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        try:
            await query.message.delete()
        except Exception: pass
        chat_id = query.message.chat_id
    else:
        if update.message:
            try:
                await update.message.delete()
            except Exception: pass
        chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text="به بخش «تنظیمات و ابزارها» بازگشتید.",
        reply_markup=get_settings_and_tools_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END