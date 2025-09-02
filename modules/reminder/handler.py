# FILE: modules/reminder/handler.py (نسخه نهایی و صحیح)

import logging
from telegram import Update
from telegram.ext import (
    Application, MessageHandler, filters, ContextTypes
)

from .actions import jobs, settings
from .actions.daily_note import daily_notes_conv
from shared.keyboards import get_notes_management_keyboard
from modules.marzban.actions import note

LOGGER = logging.getLogger(__name__)

async def show_notes_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the 'Notes Management' menu."""
    await update.message.reply_text(
        "به بخش «مدیریت یادداشت‌ها» خوش آمدید.",
        reply_markup=get_notes_management_keyboard()
    )

def register(application: Application) -> None:
    """Registers handlers for the reminder and tools module."""
    from config import config
    
    if config.AUTHORIZED_USER_IDS:
        application.bot_data['admin_id_for_jobs'] = config.AUTHORIZED_USER_IDS[0]
    else:
        LOGGER.warning("No authorized users found. Reminder job cannot be scheduled.")
        application.bot_data['admin_id_for_jobs'] = None

    # ======================== START: FIX for IndexError ========================
    # به جای جایگزینی آیتم صفرم، یک آیتم جدید به لیست خالی اضافه می‌کنیم
    settings.reminder_settings_conv.entry_points.append(
        MessageHandler(
            filters.Regex('^⚙️ اتوماسیون روزانه$'), 
            settings.start_reminder_settings
        )
    )
    # ========================= END: FIX for IndexError =========================
    
    application.add_handler(settings.reminder_settings_conv, group=1)
    application.add_handler(daily_notes_conv, group=1)
    
    application.add_handler(MessageHandler(filters.Regex('^📓 مدیریت یادداشت‌ها$'), show_notes_management_menu), group=1)
    application.add_handler(MessageHandler(filters.Regex('^👤 اشتراک‌های ثبت‌شده$'), note.list_users_with_subscriptions), group=1)

    if application.job_queue:
        application.job_queue.run_once(
            callback=lambda ctx: jobs.schedule_initial_daily_job(application),
            when=5,
            name="initial_job_scheduler"
        )