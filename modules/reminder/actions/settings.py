# --- START OF FILE modules/reminder/actions/settings.py ---
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
from database.crud import bot_setting as crud_bot_setting

LOGGER = logging.getLogger(__name__)

MENU, SET_TIME, SET_DAYS, SET_DATA, SET_GRACE_PERIOD = range(5)

async def _build_settings_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from shared.translator import _
    
    settings = await crud_bot_setting.load_bot_settings()

    time_val = settings.get('reminder_time', "09:00")
    days_val = settings.get('reminder_days', 3)
    data_val = settings.get('reminder_data_gb', 1)
    grace_val = settings.get('auto_delete_grace_days', 7)

    keyboard = [
        [InlineKeyboardButton(_("reminder_settings.button_time", time=time_val), callback_data="rem_set_time")],
        [InlineKeyboardButton(_("reminder_settings.button_days_threshold", days=days_val), callback_data="rem_set_days")],
        [InlineKeyboardButton(_("reminder_settings.button_data_threshold", gb=data_val), callback_data="rem_set_data")],
        [InlineKeyboardButton(_("reminder_settings.button_grace_period", days=grace_val), callback_data="rem_set_grace_period")],
        [InlineKeyboardButton(_("reminder_settings.button_back_to_tools"), callback_data="rem_back_to_tools")]
    ]
    text = _("reminder_settings.menu_title")

    if query := update.callback_query:
        await query.answer()
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        if update.message: await update.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN
        )

async def start_reminder_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _build_settings_message(update, context)
    return MENU

async def prompt_for_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(_("reminder_settings.prompt_time"), parse_mode=ParseMode.MARKDOWN)
    return SET_TIME

async def process_new_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    
    new_time_str = update.message.text.strip()
    try:
        new_time_obj = datetime.datetime.strptime(new_time_str, '%H:%M').time()
        await crud_bot_setting.save_bot_settings({'reminder_time': new_time_str})
        await jobs.schedule_daily_job(context.application, new_time_obj)
        await update.message.reply_text(_("reminder_settings.time_updated_success"))
    except ValueError:
        await update.message.reply_text(_("reminder_settings.invalid_time_format"))
        return SET_TIME
    await _build_settings_message(update, context)
    return MENU

async def prompt_for_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(_("reminder_settings.prompt_days"), parse_mode=ParseMode.MARKDOWN)
    return SET_DAYS

async def process_new_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    try:
        days = int(update.message.text)
        if not 1 <= days <= 30: raise ValueError
        await crud_bot_setting.save_bot_settings({'reminder_days': days})
        await update.message.reply_text(_("reminder_settings.days_updated_success", days=days))
    except (ValueError, TypeError):
        await update.message.reply_text(_("reminder_settings.invalid_days_input"))
        return SET_DAYS
    await _build_settings_message(update, context)
    return MENU

async def prompt_for_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(_("reminder_settings.prompt_data"), parse_mode=ParseMode.MARKDOWN)
    return SET_DATA

async def process_new_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    try:
        data_gb = int(update.message.text)
        if not 1 <= data_gb <= 100: raise ValueError
        await crud_bot_setting.save_bot_settings({'reminder_data_gb': data_gb})
        await update.message.reply_text(_("reminder_settings.data_updated_success", gb=data_gb))
    except (ValueError, TypeError):
        await update.message.reply_text(_("reminder_settings.invalid_data_input"))
        return SET_DATA
    await _build_settings_message(update, context)
    return MENU

async def prompt_for_grace_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(_("reminder_settings.prompt_grace_period"), parse_mode=ParseMode.MARKDOWN)
    return SET_GRACE_PERIOD

async def process_new_grace_period(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from shared.translator import _
    try:
        days = int(update.message.text)
        if not 0 <= days <= 365: raise ValueError
        await crud_bot_setting.save_bot_settings({'auto_delete_grace_days': days})
        if days > 0:
            await update.message.reply_text(_("reminder_settings.grace_period_updated_success", days=days))
        else:
            await update.message.reply_text(_("reminder_settings.grace_period_disabled"))
    except (ValueError, TypeError):
        await update.message.reply_text(_("reminder_settings.invalid_grace_period_input"))
        return SET_GRACE_PERIOD
    await _build_settings_message(update, context)
    return MENU

reminder_settings_conv = ConversationHandler(
    entry_points=[],
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
    conversation_timeout=180, per_user=True, per_chat=True
)
# --- END OF FILE modules/reminder/actions/settings.py ---