# FILE: modules/marzban/handler.py
# (نسخه نهایی و کاملاً بازنویسی شده)

from telegram.ext import (
    Application, ConversationHandler, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
)

from .actions import (
    add_user, display, modify_user, search, messaging,
    note, template, linking, credentials
)
# --- START OF CHANGE: Import the payment module ---
from modules.financials.actions import payment
# --- END OF CHANGE ---
from shared.callbacks import cancel_conversation
from modules.general.actions import start as back_to_main_menu_action
from modules.auth import admin_only, admin_only_conv

def register(application: Application) -> None:
    """Registers all handlers for the Marzban (admin) module."""

    conv_settings = {
        "fallbacks": [CommandHandler('cancel', cancel_conversation)],
        "conversation_timeout": 300, "per_chat": True, "per_user": True
    }

    # --- Conversations ---
    add_user_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^➕ افزودن کاربر$'), admin_only_conv(add_user.add_user_start)),
            CallbackQueryHandler(add_user.add_user_for_customer_start, pattern=r'^create_user_for_')
        ],
        states={
            add_user.ADD_USER_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user.add_user_get_username)],
            add_user.ADD_USER_DATALIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user.add_user_get_datalimit)],
            add_user.ADD_USER_EXPIRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_user.add_user_get_expire)],
            add_user.ADD_USER_CONFIRM: [
                CallbackQueryHandler(add_user.add_user_create, pattern='^confirm_add_user$'),
                CallbackQueryHandler(add_user.cancel_add_user, pattern='^cancel_add_user$')
            ],
        }, **conv_settings
    )
    search_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🔎 جستجوی کاربر$'), admin_only_conv(search.prompt_for_search))],
        states={search.SEARCH_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search.search_user)]},
        **conv_settings
    )
    add_data_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(modify_user.prompt_for_add_data, pattern=r'^add_data_')],
        states={modify_user.ADD_DATA_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, modify_user.process_add_data)]},
        **conv_settings
    )
    add_days_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(modify_user.prompt_for_add_days, pattern=r'^add_days_')],
        states={modify_user.ADD_DAYS_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, modify_user.process_add_days)]},
        **conv_settings
    )
    note_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(note.prompt_for_note_details, pattern=r'^note_')],
        states={
            note.GET_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, note.get_duration_and_ask_for_price)],
            note.GET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, note.get_price_and_save_note)],
        }, **conv_settings
    )
    delete_note_handler = CallbackQueryHandler(note.delete_note_from_prompt, pattern=r'^delete_note_')

    # Register all conversations
    application.add_handler(credentials.credential_conv, group=0)
    application.add_handler(add_user_conv, group=0)
    application.add_handler(search_conv, group=0)
    application.add_handler(add_data_conv, group=0)
    application.add_handler(add_days_conv, group=0)
    application.add_handler(messaging.messaging_conv, group=0)
    application.add_handler(note_conv, group=0)
    application.add_handler(delete_note_handler, group=0)

    # --- Standalone Handlers ---
    handlers = [
        MessageHandler(filters.Regex('^👤 مدیریت کاربران$'), admin_only(display.show_user_management_menu)),
        MessageHandler(filters.Regex('^👥 نمایش کاربران$'), admin_only(display.list_all_users_paginated)),
        MessageHandler(filters.Regex('^⌛️ کاربران رو به اتمام$'), admin_only(display.list_warning_users_paginated)),
        MessageHandler(filters.Regex('^🔙 بازگشت به منوی اصلی$'), admin_only(back_to_main_menu_action)),
        
        CallbackQueryHandler(display.update_user_page, pattern=r'^show_users_page_'),
        CallbackQueryHandler(display.show_user_details, pattern=r'^user_details_'),
        CallbackQueryHandler(display.close_pagination_message, pattern=r'^close_pagination$'),
        
        CallbackQueryHandler(modify_user.renew_user_smart, pattern=r'^renew_'),
        CallbackQueryHandler(modify_user.reset_user_traffic, pattern=r'^reset_traffic_'),
        CallbackQueryHandler(modify_user.confirm_delete_user, pattern=r'^delete_'),
        CallbackQueryHandler(modify_user.do_delete_user, pattern=r'^do_delete_'),
        CallbackQueryHandler(modify_user.admin_confirm_delete, pattern=r'^admin_confirm_delete_'),
        CallbackQueryHandler(modify_user.admin_reject_delete, pattern=r'^admin_reject_delete_'),
        
        # --- START OF CHANGE: Add the handler for the manual invoice button ---
        CallbackQueryHandler(payment.send_manual_invoice, pattern=r'^send_invoice_'),
        # --- END OF CHANGE ---
        
        CommandHandler("start", display.handle_deep_link_details, filters=filters.Regex(r'details_'))
    ]

    for handler in handlers:
        application.add_handler(handler, group=0)