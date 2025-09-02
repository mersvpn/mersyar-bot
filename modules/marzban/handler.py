# FILE: modules/marzban/handler.py (نسخه نهایی و اصلاح شده)

from telegram.ext import (
    Application, ConversationHandler, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
)

from .actions import (
    add_user, display, modify_user, search, messaging,
    note, template, linking, credentials
)
from modules.financials.actions import payment
from shared.callbacks import cancel_conversation
from modules.general.actions import start as back_to_main_menu_action
from shared.callbacks import cancel_conversation, cancel_to_helper_tools

def register(application: Application) -> None:
    """Registers all handlers for the Marzban (admin) module."""

    conv_settings = {
        "fallbacks": [CommandHandler('cancel', cancel_conversation)],
        "conversation_timeout": 300, "per_chat": True, "per_user": True
    }

    # --- 1. Define All Conversations for this Module ---
    add_user_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^➕ افزودن کاربر$'), add_user.add_user_start),
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
        entry_points=[MessageHandler(filters.Regex('^🔎 جستجوی کاربر$'), search.prompt_for_search)],
        states={search.SEARCH_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search.search_user)]},
        **conv_settings
    )
    
    note_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(note.prompt_for_note_details, pattern=r'^note_')],
        states={
            note.GET_DURATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, note.get_duration_and_ask_for_data_limit),
                CallbackQueryHandler(note.delete_note_from_prompt, pattern=r'^delete_note_')
            ],
            note.GET_DATA_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, note.get_data_limit_and_ask_for_price)],
            note.GET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, note.get_price_and_save_note)],
        }, **conv_settings
    )
    
    template_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^⚙️ تنظیم کاربر الگو$'), template.set_template_user_start)],
        states={template.SET_TEMPLATE_USER_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, template.set_template_user_process)]},
        fallbacks=[CommandHandler('cancel', cancel_to_helper_tools)],
        conversation_timeout=300, per_chat=True, per_user=True
    )
    
    linking_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🔗 ایجاد لینک اتصال$'), linking.start_linking_process)],
        states={linking.PROMPT_USERNAME_FOR_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, linking.generate_linking_url)]},
        fallbacks=[CommandHandler('cancel', cancel_to_helper_tools)],
        conversation_timeout=300, per_chat=True, per_user=True
    )
    
    add_days_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(modify_user.prompt_for_add_days, pattern=r'^add_days_')],
        states={modify_user.ADD_DAYS_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, modify_user.do_add_days)]},
        **conv_settings
    )
    
    add_data_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(modify_user.prompt_for_add_data, pattern=r'^add_data_')],
        states={modify_user.ADD_DATA_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, modify_user.do_add_data)]},
        **conv_settings
    )

    # --- 2. Register All Conversations ---
    application.add_handler(credentials.credential_conv, group=0)
    application.add_handler(add_user_conv, group=0)
    application.add_handler(search_conv, group=0)
    application.add_handler(messaging.messaging_conv, group=0)
    application.add_handler(note_conv, group=0)
    application.add_handler(template_conv, group=0)
    application.add_handler(linking_conv, group=0)
    application.add_handler(add_days_conv, group=0)
    application.add_handler(add_data_conv, group=0)

    # --- 3. Register Standalone Handlers ---
    handlers = [
        MessageHandler(filters.Regex('^👤 مدیریت کاربران$'), display.show_user_management_menu),
        MessageHandler(filters.Regex('^👥 نمایش کاربران$'), display.list_all_users_paginated),
        MessageHandler(filters.Regex('^⌛️ کاربران رو به اتمام$'), display.list_warning_users_paginated),
        MessageHandler(filters.Regex('^🔙 بازگشت به منوی اصلی$'), back_to_main_menu_action),
        
        CallbackQueryHandler(display.update_user_page, pattern=r'^show_users_page_'),
        CallbackQueryHandler(display.show_user_details, pattern=r'^user_details_'),
        CallbackQueryHandler(display.close_pagination_message, pattern=r'^close_pagination$'),

        CallbackQueryHandler(display.send_subscription_qr_code_and_link, pattern=r'^sub_link_'),
        
        CallbackQueryHandler(modify_user.renew_user_smart, pattern=r'^renew_'),
        CallbackQueryHandler(modify_user.reset_user_traffic, pattern=r'^reset_traffic_'),
        CallbackQueryHandler(modify_user.confirm_delete_user, pattern=r'^delete_'),
        CallbackQueryHandler(modify_user.do_delete_user, pattern=r'^do_delete_'),
        
        # --- 🟢 بخش اصلاح شده: هندلرهای اضافی حذف شدند ---
        
        CallbackQueryHandler(note.list_users_with_subscriptions, pattern=r'^list_subs_page_'),
        CallbackQueryHandler(payment.send_manual_invoice, pattern=r'^send_invoice_'),
        
        CommandHandler("start", display.handle_deep_link_details, filters=filters.Regex(r'details_'))
    ]

    for handler in handlers:
        application.add_handler(handler, group=0)