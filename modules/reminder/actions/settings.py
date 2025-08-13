# ===== IMPORTS & DEPENDENCIES =====
import datetime
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, Application, CommandHandler
)
from telegram.constants import ParseMode

# --- Local Imports ---
from . import jobs
from .constants import (
    SET_TIME_PROMPT, SET_DAYS_PROMPT, SET_DATA_PROMPT, MENU_STATE
)
# CORRECTED: Import keyboards from the new shared location
from shared.keyboards import get_settings_and_tools_keyboard
from modules.marzban.actions.data_manager import load_settings, save_settings
from modules.auth import admin_only, admin_only_conv
# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# ===== UI & MENU FUNCTIONS (NON-CONVERSATION) =====

@admin_only
async def show_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the 'Settings & Tools' main menu."""
    # This function can be called from a message or a callback query (after ending a conv)
    target = update.message or update.callback_query.message
    await target.reply_text(
        "به بخش «تنظیمات و ابزارها» خوش آمدید.",
        reply_markup=get_settings_and_tools_keyboard()
    )

# ===== HELPER FUNCTIONS & UI (CONVERSATION-SPECIFIC) =====

async def build_settings_keyboard() -> InlineKeyboardMarkup:
    """Builds the settings keyboard dynamically by loading current settings."""
    settings = await load_settings()
    time_button = InlineKeyboardButton(f"⏰ ساعت اعلان: {settings['reminder_time']}", callback_data="rem_set_time")
    days_button = InlineKeyboardButton(f"⏳ آستانه روز: {settings['reminder_days']} روز", callback_data="rem_set_days")
    data_button = InlineKeyboardButton(f"📉 آستانه حجم: {settings['reminder_data_gb']} گیگابایت", callback_data="rem_set_data")
    back_button = InlineKeyboardButton("🔙 بازگشت به ابزارها", callback_data="rem_back_to_tools")

    return InlineKeyboardMarkup([[time_button], [days_button], [data_button], [back_button]])

# ===== CONVERSATION HANDLER FUNCTIONS =====

async def start_reminder_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for the reminder settings conversation. Displays the main menu."""
    keyboard = await build_settings_keyboard()
    message_text = "⚙️ **تنظیمات یادآور خودکار**\n\nاز این منو می‌توانید پارامترهای اعلان روزانه را مدیریت کنید."

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(message_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN)

    return MENU_STATE

async def back_to_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    CORRECTED & ROBUST EXIT: Ends the conversation and shows the tools menu.
    """
    query = update.callback_query
    await query.answer()
    # Delete the settings menu message to clean up the chat.
    await query.message.delete()
    # Call the standalone function to show the tools menu.
    await show_tools_menu(update, context)
    # Clear any leftover data from the conversation.
    context.user_data.clear()
    # Explicitly end the conversation.
    return ConversationHandler.END

# --- Prompts and Processors (No changes needed in these) ---
async def prompt_for_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    await query.edit_message_text("لطفاً ساعت جدید ارسال اعلان روزانه را به وقت تهران وارد کنید.\n(فرمت: `HH:MM`, مثلاً `11:30`)", parse_mode=ParseMode.MARKDOWN)
    return SET_TIME_PROMPT

async def process_new_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_time_str = update.message.text.strip()
    try:
        new_time_obj = datetime.datetime.strptime(new_time_str, '%H:%M').time()
        settings_data = await load_settings()
        settings_data['reminder_time'] = new_time_str
        await save_settings(settings_data)
        await jobs.schedule_daily_job(context.application, new_time_obj)
        await update.message.reply_text("✅ ساعت اعلان با موفقیت به‌روزرسانی و جاب زمان‌بندی مجدد شد.")
        await start_reminder_settings(update, context) # Go back to the menu
        return MENU_STATE
    except ValueError:
        await update.message.reply_text("❌ فرمت نامعتبر است. لطفاً دوباره در فرمت HH:MM وارد کنید.")
        return SET_TIME_PROMPT

async def prompt_for_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    await query.edit_message_text("لطفاً آستانه جدید برای **روزهای باقی‌مانده** را وارد کنید (مثلاً `3`):", parse_mode=ParseMode.MARKDOWN)
    return SET_DAYS_PROMPT

async def process_new_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        days = int(update.message.text)
        if not 1 <= days <= 30: raise ValueError()
        settings_data = await load_settings()
        settings_data['reminder_days'] = days
        await save_settings(settings_data)
        await update.message.reply_text(f"✅ آستانه روز به {days} روز تغییر یافت.")
        await start_reminder_settings(update, context)
        return MENU_STATE
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً یک عدد صحیح وارد کنید.")
        return SET_DAYS_PROMPT

async def prompt_for_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    await query.edit_message_text("لطفاً آستانه جدید برای **حجم باقی‌مانده** را به **گیگابایت** وارد کنید (مثلاً `1`):", parse_mode=ParseMode.MARKDOWN)
    return SET_DATA_PROMPT

async def process_new_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        data_gb = int(update.message.text)
        if not 1 <= data_gb <= 100: raise ValueError()
        settings_data = await load_settings()
        settings_data['reminder_data_gb'] = data_gb
        await save_settings(settings_data)
        await update.message.reply_text(f"✅ آستانه حجم به {data_gb} گیگابایت تغییر یافت.")
        await start_reminder_settings(update, context)
        return MENU_STATE
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً یک عدد صحیح وارد کنید.")
        return SET_DATA_PROMPT


# --- EXPORTED CONVERSATION HANDLER ---
reminder_settings_conv = ConversationHandler(
    # Use the secure conversation entry point decorator
    entry_points=[MessageHandler(filters.Regex('^⏰ تنظیمات یادآور$'), admin_only_conv(start_reminder_settings))],
    states={
        MENU_STATE: [
            CallbackQueryHandler(prompt_for_time, pattern='^rem_set_time$'),
            CallbackQueryHandler(prompt_for_days, pattern='^rem_set_days$'),
            CallbackQueryHandler(prompt_for_data, pattern='^rem_set_data$'),
            # This is now the primary and robust exit point for the conversation
            CallbackQueryHandler(back_to_tools_menu, pattern='^rem_back_to_tools$'),
        ],
        SET_TIME_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_time)],
        SET_DAYS_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_days)],
        SET_DATA_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_data)],
    },
    # A generic cancel command is a good fallback
    fallbacks=[CommandHandler('cancel', back_to_tools_menu)],
    conversation_timeout=300
)