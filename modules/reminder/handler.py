
import logging
from telegram.ext import (
    Application, ConversationHandler, CommandHandler,
    MessageHandler, filters, CallbackQueryHandler
)

# --- Local Imports ---
from modules.marzban.actions import note, template, linking
from shared.callbacks import cancel_conversation
from .actions import jobs, settings
from .actions.daily_note import daily_notes_conv
from modules.general.actions import start as back_to_main_menu


LOGGER = logging.getLogger(__name__)

def register(application: Application) -> None:
    from config import config
    from modules.marzban.actions import note
    
    if config.AUTHORIZED_USER_IDS:
        application.bot_data['admin_id_for_jobs'] = config.AUTHORIZED_USER_IDS[0]
    else:
        LOGGER.warning("No authorized users found. Reminder job cannot be scheduled.")
        application.bot_data['admin_id_for_jobs'] = None

    conv_settings = {
        "fallbacks": [CommandHandler('cancel', cancel_conversation)],
        "conversation_timeout": 600, "per_chat": True, "per_user": True
    }
    
    # --- Conversation Handlers Definition ---
    template_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^⚙️ تنظیم کاربر الگو$'), template.set_template_user_start)],
        states={template.SET_TEMPLATE_USER_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, template.set_template_user_process)]},
        **conv_settings
    )
    linking_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🔗 ایجاد لینک اتصال$'), linking.start_linking_process)],
        states={linking.PROMPT_USERNAME_FOR_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, linking.generate_linking_url)]},
        **conv_settings
    )
    note_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(note.prompt_for_note, pattern=r'^note_')],
        states={
            note.NOTE_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, note.save_user_note)]
        },
        fallbacks=[
            CommandHandler('start', back_to_main_menu),
            MessageHandler(filters.Regex('^🔙 بازگشت به منوی اصلی$'), back_to_main_menu),
            MessageHandler(filters.Regex('^(👤 مدیریت کاربران|📓 مدیریت یادداشت‌ها|📨 ارسال پیام|⚙️ تنظیمات و ابزارها|💻 ورود به پنل کاربری|ℹ️ راهنما)$'), back_to_main_menu)
        ],
        conversation_timeout=300,
        per_user=True,
        per_chat=True,
        allow_reentry=True # <-- This line is the key fix
    )

    # --- Handlers Registration ---
    application.add_handler(settings.reminder_settings_conv, group=0)
    application.add_handler(daily_notes_conv, group=0)
    application.add_handler(template_conv, group=0)
    application.add_handler(linking_conv, group=0)
    application.add_handler(note_conv, group=0)
    
    # Standalone menu handlers
    application.add_handler(MessageHandler(filters.Regex('^⚙️ تنظیمات و ابزارها$'), settings.show_tools_menu), group=0)
    application.add_handler(MessageHandler(filters.Regex('^📓 مدیریت یادداشت‌ها$'), settings.show_notes_management_menu), group=0)
    
    # Standalone action handlers
    application.add_handler(MessageHandler(filters.Regex('^📝 پیگیری‌های فعال$'), note.list_active_reminders), group=0)
    application.add_handler(CallbackQueryHandler(note.delete_note_callback, pattern=r'^del_note_'), group=0)

    # Schedule Jobs
    if application.job_queue:
        application.job_queue.run_once(lambda ctx: jobs.schedule_initial_daily_job(application), when=2, name="initial_job_scheduler")