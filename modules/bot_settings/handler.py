# FILE: modules/bot_settings/handler.py (نسخه نهایی با حذف هندلر زائد)

from telegram import Update
from telegram.ext import (
    Application, ConversationHandler, MessageHandler, 
    filters, CallbackQueryHandler, CommandHandler, ContextTypes
)
from modules.auth import admin_only_conv, admin_only
from shared.keyboards import get_settings_and_tools_keyboard
from .actions import (
    start_bot_settings,
    toggle_maintenance_mode,
    toggle_log_channel,
    toggle_wallet_status, 
    back_to_tools,
    show_helper_tools_menu,
    back_to_settings_menu,
    prompt_for_channel_id,
    process_channel_id,
    MENU_STATE,
    SET_CHANNEL_ID,
)

async def show_settings_and_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the main 'Settings and Tools' menu."""
    await update.message.reply_text(
        "به بخش «تنظیمات و ابزارها» خوش آمدید.",
        reply_markup=get_settings_and_tools_keyboard()
    )

def register(application: Application) -> None:
    bot_settings_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🔧 تنظیمات ربات$'), admin_only_conv(start_bot_settings))],
        states={
            MENU_STATE: [
                CallbackQueryHandler(toggle_maintenance_mode, pattern=r'^toggle_maintenance_'),
                CallbackQueryHandler(toggle_log_channel, pattern=r'^toggle_log_channel_'),
                CallbackQueryHandler(toggle_wallet_status, pattern=r'^toggle_wallet_'),
                CallbackQueryHandler(back_to_tools, pattern=r'^bot_status_back$'),
            ]
        },
        fallbacks=[CommandHandler('cancel', back_to_tools)],
        conversation_timeout=300
    )
    
    channel_id_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📣 تنظیم کانال گزارش$'), admin_only_conv(prompt_for_channel_id))],
        states={
            SET_CHANNEL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_channel_id)]
        },
        fallbacks=[CommandHandler('cancel', back_to_tools)],
        conversation_timeout=300
    )
    
    # ثبت هندلر اصلی برای منوی تنظیمات
    application.add_handler(MessageHandler(filters.Regex('^⚙️ تنظیمات و ابزارها$'), admin_only(show_settings_and_tools_menu)), group=0)

    # ثبت مکالمات
    application.add_handler(bot_settings_conv, group=0)
    application.add_handler(channel_id_conv, group=0)

    # ثبت هندلرهای مستقل برای منوی ابزارهای کمکی
    application.add_handler(MessageHandler(filters.Regex('^🛠️ ابزارهای کمکی$'), admin_only(show_helper_tools_menu)), group=0)
    application.add_handler(MessageHandler(filters.Regex('^🔙 بازگشت به تنظیمات$'), admin_only(back_to_settings_menu)), group=0)