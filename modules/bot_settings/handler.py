from telegram.ext import (
    Application, ConversationHandler, MessageHandler, 
    filters, CallbackQueryHandler, CommandHandler
)
from modules.auth import admin_only_conv
from .actions import (
    start_bot_settings,
    toggle_bot_status,
    back_to_tools,
    MENU_STATE,
)

def register(application: Application) -> None:
    
    bot_settings_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🔧 تنظیمات ربات$'), admin_only_conv(start_bot_settings))],
        states={
            MENU_STATE: [
                CallbackQueryHandler(toggle_bot_status, pattern=r'^bot_status_(de)?activate$'),
                CallbackQueryHandler(back_to_tools, pattern='^bot_status_back$'),
            ]
        },
        fallbacks=[CommandHandler('cancel', back_to_tools)],
        conversation_timeout=300,
        per_user=True,
        per_chat=True
    )

    application.add_handler(bot_settings_conv, group=0)