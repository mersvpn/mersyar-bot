import datetime
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, CommandHandler
)
from shared.keyboards import get_notes_management_keyboard
from telegram.constants import ParseMode
from . import jobs
from shared.keyboards import get_settings_and_tools_keyboard
from modules.marzban.actions.data_manager import load_settings, save_settings
from modules.auth import admin_only, admin_only_conv

LOGGER = logging.getLogger(__name__)

(
    MENU, SET_TIME, SET_DAYS, SET_DATA
) = range(4)

async def _build_settings_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = await load_settings()
    keyboard = [
        [InlineKeyboardButton(f"⏰ ساعت اعلان: {settings['reminder_time']}", callback_data="rem_set_time")],
        [InlineKeyboardButton(f"⏳ آستانه روز: {settings['reminder_days']} روز", callback_data="rem_set_days")],
        [InlineKeyboardButton(f"📉 آستانه حجم: {settings['reminder_data_gb']} گیگابایت", callback_data="rem_set_data")],
        [InlineKeyboardButton("🔙 بازگشت به ابزارها", callback_data="rem_back_to_tools")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "⚙️ **تنظیمات یادآور خودکار**\n\nاز این منو می‌توانید پارامترهای اعلان روزانه را مدیریت کنید."

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

@admin_only
async def show_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = update.message or (update.callback_query and update.callback_query.message)
    await target.reply_text(
        "به بخش «تنظیمات و ابزارها» خوش آمدید.",
        reply_markup=get_settings_and_tools_keyboard()
    )

async def start_reminder_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['settings_message'] = update.message
    await _build_settings_message(update, context)
    return MENU

async def prompt_for_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "لطفاً ساعت جدید ارسال اعلان روزانه را به وقت تهران وارد کنید.\n(فرمت: `HH:MM`, مثلاً `11:30`)",
        parse_mode=ParseMode.MARKDOWN
    )
    return SET_TIME

async def process_new_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_time_str = update.message.text.strip()
    try:
        new_time_obj = datetime.datetime.strptime(new_time_str, '%H:%M').time()
        settings = await load_settings()
        settings['reminder_time'] = new_time_str
        await save_settings(settings)
        await jobs.schedule_daily_job(context.application, new_time_obj)
        await update.message.reply_text("✅ ساعت اعلان با موفقیت به‌روزرسانی شد.")
    except ValueError:
        await update.message.reply_text("❌ فرمت نامعتبر است. لطفاً دوباره در فرمت HH:MM وارد کنید.")
        return SET_TIME
    
    await _build_settings_message(update, context)
    return MENU

async def prompt_for_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "لطفاً آستانه جدید برای **روزهای باقی‌مانده** را وارد کنید (مثلاً `3`):",
        parse_mode=ParseMode.MARKDOWN
    )
    return SET_DAYS

async def process_new_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        days = int(update.message.text)
        if not 1 <= days <= 30: raise ValueError
        settings = await load_settings()
        settings['reminder_days'] = days
        await save_settings(settings)
        await update.message.reply_text(f"✅ آستانه روز به {days} روز تغییر یافت.")
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً یک عدد صحیح بین ۱ تا ۳۰ وارد کنید.")
        return SET_DAYS
    
    await _build_settings_message(update, context)
    return MENU

async def prompt_for_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "لطفاً آستانه جدید برای **حجم باقی‌مانده** را به **گیگابایت** وارد کنید (مثلاً `1`):",
        parse_mode=ParseMode.MARKDOWN
    )
    return SET_DATA

async def process_new_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        data_gb = int(update.message.text)
        if not 1 <= data_gb <= 100: raise ValueError
        settings = await load_settings()
        settings['reminder_data_gb'] = data_gb
        await save_settings(settings)
        await update.message.reply_text(f"✅ آستانه حجم به {data_gb} گیگابایت تغییر یافت.")
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً یک عدد صحیح بین ۱ تا ۱۰۰ وارد کنید.")
        return SET_DATA

    await _build_settings_message(update, context)
    return MENU

async def back_to_tools(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.message.delete()
    await show_tools_menu(update, context)
    context.user_data.clear()
    return ConversationHandler.END

reminder_settings_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^⏰ تنظیمات یادآور$'), admin_only_conv(start_reminder_settings))],
    states={
        MENU: [
            CallbackQueryHandler(prompt_for_time, pattern='^rem_set_time$'),
            CallbackQueryHandler(prompt_for_days, pattern='^rem_set_days$'),
            CallbackQueryHandler(prompt_for_data, pattern='^rem_set_data$'),
            CallbackQueryHandler(back_to_tools, pattern='^rem_back_to_tools$'),
        ],
        SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_time)],
        SET_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_days)],
        SET_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_data)],
    },
    fallbacks=[CommandHandler('cancel', back_to_tools)],
    conversation_timeout=300,
    per_user=True,
    per_chat=True
)
async def show_notes_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "به بخش «مدیریت یادداشت‌ها» خوش آمدید.",
        reply_markup=get_notes_management_keyboard()
    )