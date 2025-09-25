# FILE: modules/marzban/handler.py (FINAL REVISION WITH MISSING HANDLER)

from telegram.ext import (
    Application, ConversationHandler, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
)
from shared.translator import _ as t
import re
# --- Local Imports ---
from .actions import (
    add_user, display, modify_user, search, messaging,
    note, template, linking, credentials
)
from modules.payment.actions import renewal as payment_actions
from modules.general.actions import switch_to_customer_view
from shared.callbacks import cancel_to_helper_tools
from config import config  # Import config to access admin IDs
from shared.callbacks import end_conversation_and_show_menu
# V V V V V ADD BOTH OF THESE LINES HERE V V V V V
# A regex pattern that matches all buttons on the user management submenu
USER_MANAGEMENT_BUTTONS_REGEX = r'^(👥 نمایش کاربران|⌛️ کاربران رو به اتمام|🔎 جستجوی کاربر|➕ افزودن کاربر|🔙 بازگشت به منوی اصلی)$'

# A regex for main admin menu buttons that could interrupt a conversation
ADMIN_MAIN_MENU_REGEX = r'^(👤 مدیریت کاربران|📓 مدیریت یادداشت‌ها|⚙️ تنظیمات و ابزارها|📨 ارسال پیام|💻 ورود به پنل کاربری|📚 تنظیمات آموزش|🔙 بازگشت به منوی اصلی)$'
# ^ ^ ^ ^ ^ ADD BOTH OF THESE LINES HERE ^ ^ ^ ^ ^

def register(application: Application) -> None:
    """Registers all handlers for the Marzban (admin) module."""

    # This filter will be used for all standalone admin buttons
    admin_filter = filters.User(user_id=config.AUTHORIZED_USER_IDS)

    conv_settings = {
        "fallbacks": [CommandHandler('cancel', end_conversation_and_show_menu)],
        "conversation_timeout": 300, "per_chat": True, "per_user": True
    }

    # --- 1. Define All Conversations for this Module ---
    add_user_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^➕ افزودن کاربر$') & admin_filter, add_user.add_user_start),
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
        entry_points=[MessageHandler(filters.Regex('^🔎 جستجوی کاربر$') & admin_filter, search.prompt_for_search)],
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
        entry_points=[MessageHandler(filters.Regex('^⚙️ تنظیم کاربر الگو$') & admin_filter, template.set_template_user_start)],
        states={template.SET_TEMPLATE_USER_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, template.set_template_user_process)]},
        fallbacks=[CommandHandler('cancel', cancel_to_helper_tools)],
        conversation_timeout=300, per_chat=True, per_user=True
    )
    
    linking_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🔗 ایجاد لینک اتصال$') & admin_filter, linking.start_linking_process)],
        states={linking.PROMPT_USERNAME_FOR_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, linking.generate_linking_url)]},
        fallbacks=[CommandHandler('cancel', cancel_to_helper_tools)],
        conversation_timeout=300, per_chat=True, per_user=True
    )


# FILE: modules/marzban/handler.py
# REPLACE BOTH CONVERSATION HANDLERS

    add_days_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(modify_user.prompt_for_add_days, pattern=r'^add_days_')],
        states={
            modify_user.ADD_DAYS_PROMPT: [MessageHandler(
                filters.TEXT & ~filters.COMMAND & ~filters.Regex(ADMIN_MAIN_MENU_REGEX), 
                modify_user.do_add_days
            )]
        },
        fallbacks=[
            MessageHandler(filters.Regex('^🔙 بازگشت به منوی اصلی$'), end_conversation_and_show_menu),
            CommandHandler('cancel', end_conversation_and_show_menu)
        ],
        conversation_timeout=300, per_chat=True, per_user=True
    )
    
    add_data_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(modify_user.prompt_for_add_data, pattern=r'^add_data_')],
        states={
            modify_user.ADD_DATA_PROMPT: [MessageHandler(
                filters.TEXT & ~filters.COMMAND & ~filters.Regex(ADMIN_MAIN_MENU_REGEX), 
                modify_user.do_add_data
            )]
        },
        fallbacks=[
            MessageHandler(filters.Regex('^🔙 بازگشت به منوی اصلی$'), end_conversation_and_show_menu),
            CommandHandler('cancel', end_conversation_and_show_menu)
        ],
        conversation_timeout=300, per_chat=True, per_user=True
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
    
    # V V V NEW HANDLER ADDED HERE V V V
    application.add_handler(MessageHandler(filters.Regex('^💻 ورود به پنل کاربری$') & admin_filter, switch_to_customer_view), group=0)
    # ^ ^ ^ NEW HANDLER ADDED HERE ^ ^ ^

    handlers = [
        MessageHandler(filters.Regex('^👤 مدیریت کاربران$') & admin_filter, display.show_user_management_menu),
        MessageHandler(filters.Regex('^👥 نمایش کاربران$') & admin_filter, display.list_all_users_paginated),
        MessageHandler(filters.Regex('^⌛️ کاربران رو به اتمام$') & admin_filter, display.list_warning_users_paginated),
        
        CallbackQueryHandler(display.show_status_legend, pattern=r'^show_status_legend$'),
        CallbackQueryHandler(display.update_user_page, pattern=r'^show_users_page_'),
        CallbackQueryHandler(display.show_user_details, pattern=r'^user_details_'),
        CallbackQueryHandler(display.close_pagination_message, pattern=r'^close_pagination$'),

        CallbackQueryHandler(display.send_subscription_qr_code_and_link, pattern=r'^sub_link_'),
        
        CallbackQueryHandler(payment_actions.send_manual_invoice, pattern=r'^renew_'),
        CallbackQueryHandler(modify_user.reset_user_traffic, pattern=r'^reset_traffic_'),
        CallbackQueryHandler(modify_user.confirm_delete_user, pattern=r'^delete_'),
        CallbackQueryHandler(modify_user.do_delete_user, pattern=r'^do_delete_'),
        
        CallbackQueryHandler(note.list_users_with_subscriptions, pattern=r'^list_subs_page_'),
        CallbackQueryHandler(payment_actions.send_manual_invoice, pattern=r'^send_invoice_'),
        
        CommandHandler("start", display.handle_deep_link_details, filters=filters.Regex(r'details_'))
    ]

    for handler in handlers:
        application.add_handler(handler, group=0)