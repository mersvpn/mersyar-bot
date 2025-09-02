# FILE: modules/reminder/actions/settings.py (نسخه نهایی با قابلیت دوره ارفاق)

import datetime
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, CommandHandler
)
from telegram.constants import ParseMode
from shared.callbacks import cancel_to_helper_tools
from . import jobs
from shared.keyboards import get_settings_and_tools_keyboard

LOGGER = logging.getLogger(__name__)

# وضعیت‌های جدید مکالمه
MENU, SET_TIME, SET_DAYS, SET_DATA, SET_GRACE_PERIOD = range(5)

DEFAULT_SETTINGS = {
    'reminder_time': '09:00',
    'reminder_days': 3,
    'reminder_data_gb': 1,
    'auto_delete_grace_days': 7
}

async def _build_settings_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.db_manager import load_bot_settings
    db_settings = await load_bot_settings()
    settings = {**DEFAULT_SETTINGS, **db_settings}

    keyboard = [
        [InlineKeyboardButton(f"⏰ ساعت اعلان: {settings['reminder_time']}", callback_data="rem_set_time")],
        [InlineKeyboardButton(f"⏳ آستانه روز: {settings['reminder_days']} روز", callback_data="rem_set_days")],
        [InlineKeyboardButton(f"📉 آستانه حجم: {settings['reminder_data_gb']} گیگابایت", callback_data="rem_set_data")],
        [InlineKeyboardButton(f"🗑️ دوره ارفاق حذف: {settings['auto_delete_grace_days']} روز", callback_data="rem_set_grace_period")],
        [InlineKeyboardButton("🔙 بازگشت به ابزارها", callback_data="rem_back_to_tools")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "⚙️ **تنظیمات اتوماسیون روزانه**\n\nاز این منو می‌توانید پارامترهای وظایف خودکار روزانه را مدیریت کنید."

    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    else:
        if update.message: await update.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN
        )

async def start_reminder_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _build_settings_message(update, context)
    return MENU

# (توابع دیگر تا انتها بدون تغییر)
async def prompt_for_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("لطفاً ساعت جدید ارسال اعلان روزانه را به وقت تهران وارد کنید.\n(فرمت: `HH:MM`, مثلاً `11:30`)\n\nبرای لغو /cancel را ارسال کنید.", parse_mode=ParseMode.MARKDOWN)
    return SET_TIME

async def process_new_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database.db_manager import save_bot_settings
    new_time_str = update.message.text.strip()
    try:
        new_time_obj = datetime.datetime.strptime(new_time_str, '%H:%M').time()
        await save_bot_settings({'reminder_time': new_time_str})
        await jobs.schedule_daily_job(context.application, new_time_obj)
        await update.message.reply_text("✅ ساعت اعلان با موفقیت به‌روزرسانی شد.")
    except ValueError:
        await update.message.reply_text("❌ فرمت نامعتبر است. لطفاً دوباره در فرمت HH:MM وارد کنید.")
        return SET_TIME
    await _build_settings_message(update, context)
    return MENU

async def prompt_for_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("لطفاً آستانه جدید برای **روزهای باقی‌مانده** را وارد کنید (مثلاً `3`).\n\nبرای لغو /cancel را ارسال کنید.", parse_mode=ParseMode.MARKDOWN)
    return SET_DAYS

async def process_new_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database.db_manager import save_bot_settings
    try:
        days = int(update.message.text)
        if not 1 <= days <= 30: raise ValueError
        await save_bot_settings({'reminder_days': days})
        await update.message.reply_text(f"✅ آستانه روز به {days} روز تغییر یافت.")
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً یک عدد صحیح بین ۱ تا ۳۰ وارد کنید.")
        return SET_DAYS
    await _build_settings_message(update, context)
    return MENU

async def prompt_for_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("لطفاً آستانه جدید برای **حجم باقی‌مانده** را به **گیگابایت** وارد کنید (مثلاً `1`)\n\nبرای لغو /cancel را ارسال کنید.", parse_mode=ParseMode.MARKDOWN)
    return SET_DATA

async def process_new_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database.db_manager import save_bot_settings
    try:
        data_gb = int(update.message.text)
        if not 1 <= data_gb <= 100: raise ValueError
        await save_bot_settings({'reminder_data_gb': data_gb})
        await update.message.reply_text(f"✅ آستانه حجم به {data_gb} گیگابایت تغییر یافت.")
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً یک عدد صحیح بین ۱ تا ۱۰۰ وارد کنید.")
        return SET_DATA
    await _build_settings_message(update, context)
    return MENU

async def prompt_for_grace_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "لطفاً تعداد **روزهای دوره ارفاق** را وارد کنید.\n\n"
        "کاربران منقضی شده پس از گذشت این تعداد روز به صورت خودکار حذف خواهند شد.\n"
        "(برای غیرفعال کردن حذف خودکار، عدد `0` را وارد کنید)\n\n"
        "برای لغو /cancel را ارسال کنید.",
        parse_mode=ParseMode.MARKDOWN
    )
    return SET_GRACE_PERIOD

async def process_new_grace_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from database.db_manager import save_bot_settings
    try:
        days = int(update.message.text)
        if not 0 <= days <= 365: raise ValueError
        await save_bot_settings({'auto_delete_grace_days': days})
        if days > 0:
            await update.message.reply_text(f"✅ دوره ارفاق به {days} روز تغییر یافت.")
        else:
            await update.message.reply_text("✅ حذف خودکار کاربران منقضی شده، غیرفعال شد.")
    except (ValueError, TypeError):
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً یک عدد صحیح بین ۰ تا ۳۶۵ وارد کنید.")
        return SET_GRACE_PERIOD
    await _build_settings_message(update, context)
    return MENU

reminder_settings_conv = ConversationHandler(
    entry_points=[], # Entry point is now set dynamically in handler.py
    states={
        MENU: [
            CallbackQueryHandler(prompt_for_time, pattern='^rem_set_time$'),
            CallbackQueryHandler(prompt_for_days, pattern='^rem_set_days$'),
            CallbackQueryHandler(prompt_for_data, pattern='^rem_set_data$'),
            CallbackQueryHandler(prompt_for_grace_period, pattern='^rem_set_grace_period$'),
            CallbackQueryHandler(cancel_to_helper_tools, pattern='^rem_back_to_tools$'),
        ],
        SET_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_time)],
        SET_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_days)],
        SET_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_data)],
        SET_GRACE_PERIOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_grace_period)],
    },
    fallbacks=[CommandHandler('cancel', cancel_to_helper_tools)],
    conversation_timeout=180,
    per_user=True,
    per_chat=True
)