# ===== IMPORTS & DEPENDENCIES =====
import logging
from telegram.ext import (
    Application, ConversationHandler, CommandHandler,
    MessageHandler, filters, CallbackQueryHandler
)

# --- Local Imports ---
from modules.marzban.actions import note, template, linking
from shared.callbacks import cancel_conversation
from .actions import jobs
from .actions.settings import reminder_settings_conv, show_tools_menu
from .actions.daily_note import daily_note_conv

# --- Setup ---
LOGGER = logging.getLogger(__name__)

# ===== REGISTRATION =====
def register(application: Application) -> None:
    """Registers all handlers and jobs for the reminder & tools module."""

    from config import config
    if config.AUTHORIZED_USER_IDS:
        application.bot_data['admin_id_for_jobs'] = config.AUTHORIZED_USER_IDS[0]
    else:
        LOGGER.warning("⚠️ No authorized users found. Reminder job cannot be scheduled.")
        application.bot_data['admin_id_for_jobs'] = None

    standard_fallbacks = [CommandHandler('cancel', cancel_conversation)]
    conv_settings = {
        "fallbacks": standard_fallbacks,
        "conversation_timeout": 600,
        "per_chat": True,
        "per_user": True
    }

    # --- Conversation Handlers ---
    template_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^⚙️ تنظیم کاربر الگو$'), template.set_template_user_start)],
        states={
            template.SET_TEMPLATE_USER_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, template.set_template_user_process)]
        },
        **conv_settings
    )

    linking_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🔗 ایجاد لینک اتصال$'), linking.start_linking_process)],
        states={
            linking.PROMPT_USERNAME_FOR_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, linking.generate_linking_url)]
        },
        **conv_settings
    )

    note_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(note.prompt_for_note, pattern=r'^note_')],
        states={
            note.NOTE_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, note.save_user_note)]
        },
        **conv_settings
    )

    application.add_handler(template_conv, group=0)
    application.add_handler(linking_conv, group=0)
    application.add_handler(note_conv, group=0)
    application.add_handler(reminder_settings_conv, group=0)
    application.add_handler(daily_note_conv, group=0)

    # --- Standalone Handlers ---
    application.add_handler(MessageHandler(filters.Regex('^⚙️ تنظیمات و ابزارها$'), show_tools_menu), group=0)
    application.add_handler(MessageHandler(filters.Regex('^📝 پیگیری‌های فعال$'), note.list_active_reminders), group=0)
    application.add_handler(CallbackQueryHandler(note.delete_note_callback, pattern=r'^del_note_'), group=0)

    # --- Schedule the Daily Job ---
    async def schedule_initial_job_task(context):
        await jobs.schedule_initial_daily_job(application)

    if application.job_queue:
        application.job_queue.run_once(schedule_initial_job_task, when=2, name="initial_job_scheduler")