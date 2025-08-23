# FILE: modules/reminder/handler.py
# (کد کامل و نهایی‌شده برای جایگزینی)

import logging
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
)

# --- Local Imports ---
# NOTE: We are removing imports from marzban.actions, as this module should not handle them.
from modules.marzban.actions import note
from .actions import jobs, settings
from .actions.daily_note import daily_notes_conv

LOGGER = logging.getLogger(__name__)

def register(application: Application) -> None:
    """Registers handlers for the reminder and tools module."""
    from config import config
    
    # Set up a bot_data variable for the reminder job
    if config.AUTHORIZED_USER_IDS:
        application.bot_data['admin_id_for_jobs'] = config.AUTHORIZED_USER_IDS[0]
    else:
        LOGGER.warning("No authorized users found. Reminder job cannot be scheduled.")
        application.bot_data['admin_id_for_jobs'] = None

    # --- Register Handlers specific to this module ---
    # Conversations for reminder settings and daily admin notes
    application.add_handler(settings.reminder_settings_conv, group=1) # Use group 1 to avoid conflicts
    application.add_handler(daily_notes_conv, group=1)
    
    # Standalone menu handlers for tools and notes management
    application.add_handler(MessageHandler(filters.Regex('^⚙️ تنظیمات و ابزارها$'), settings.show_tools_menu), group=1)
    application.add_handler(MessageHandler(filters.Regex('^📓 مدیریت یادداشت‌ها$'), settings.show_notes_management_menu), group=1)
    
    # --- IMPORTANT: The following handlers are related to the OLD note system ---
    # They should ideally be moved or refactored. For now, we assume they are not needed
    # by the new structured note system. If you need a list of users with notes,
    # a new function will be required.
    application.add_handler(MessageHandler(filters.Regex('^👤 اشتراک‌های ثبت‌شده$'), note.list_users_with_subscriptions), group=1)
    
    # --- Schedule Jobs ---
    # Ensure the job queue exists before scheduling
    if application.job_queue:
        # Schedule the job to run once shortly after startup to set the daily schedule
        application.job_queue.run_once(
            callback=lambda ctx: jobs.schedule_initial_daily_job(application),
            when=5,  # Run 5 seconds after startup
            name="initial_job_scheduler"
        )