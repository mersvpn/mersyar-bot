# modules/marzban/handler.py
# (کد کامل و بهینه شده)

# ===== IMPORTS & DEPENDENCIES =====
from telegram.ext import (
    Application, ConversationHandler, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
)

# --- Local Imports ---
# ماژول credentials به لیست ایمپورت‌ها اضافه شد
from .actions import (
    add_user, display, modify_user, search, messaging,
    note, template, linking, credentials
)
from shared.callbacks import cancel_conversation
from modules.general.actions import start as back_to_main_menu
from modules.auth import admin_only, admin_only_conv

# ===== REGISTRATION =====
def register(application: Application) -> None:
    """Registers all handlers for the Marzban (admin) module."""

    standard_fallbacks = [CommandHandler('cancel', cancel_conversation)]
    conv_settings = {
        "fallbacks": standard_fallbacks,
        "conversation_timeout": 600,
        "per_chat": True,
        "per_user": True
    }

    # --- 1. تعریف تمام مکالمه‌ها (Conversations) ---
    # تمام ConversationHandler ها در این بخش تعریف می‌شوند

    credential_conv = credentials.credential_conv # <-- مکالمه جدید اضافه شد

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
        },
        **conv_settings
    )

    search_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🔎 جستجوی کاربر$'), admin_only_conv(search.prompt_for_search))],
        states={
            search.SEARCH_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search.search_user)]
        },
        **conv_settings
    )

    add_data_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(modify_user.prompt_for_add_data, pattern=r'^add_data_')],
        states={
            modify_user.ADD_DATA_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, modify_user.process_add_data)]
        },
        **conv_settings
    )

    add_days_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(modify_user.prompt_for_add_days, pattern=r'^add_days_')],
        states={
            modify_user.ADD_DAYS_PROMPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, modify_user.process_add_days)]
        },
        **conv_settings
    )

    # --- 2. ثبت تمام هندلرها (Handlers) ---
    # تمام add_handler ها در این بخش ثبت می‌شوند

    # ثبت مکالمه‌ها (گروه 0 برای ادمین)
    application.add_handler(credential_conv, group=0)
    application.add_handler(add_user_conv, group=0)
    application.add_handler(search_conv, group=0)
    application.add_handler(add_data_conv, group=0)
    application.add_handler(add_days_conv, group=0)
    application.add_handler(messaging.messaging_conv, group=0)

    # ثبت هندلرهای مستقل (Standalone)
    application.add_handler(MessageHandler(filters.Regex('^👤 مدیریت کاربران$'), display.show_user_management_menu), group=0)
    application.add_handler(MessageHandler(filters.Regex('^👥 نمایش کاربران$'), display.list_all_users_paginated), group=0)
    application.add_handler(MessageHandler(filters.Regex('^⌛️ کاربران رو به اتمام$'), display.list_warning_users_paginated), group=0)
    application.add_handler(MessageHandler(filters.Regex('^🔙 بازگشت به منوی اصلی$'), back_to_main_menu), group=0)
    application.add_handler(CallbackQueryHandler(display.update_user_page, pattern=r'^page_'), group=0)
    application.add_handler(CallbackQueryHandler(display.show_user_details, pattern=r'^user_details_'), group=0)
    application.add_handler(CallbackQueryHandler(display.close_pagination_message, pattern=r'^close_pagination$'), group=0)
    application.add_handler(CallbackQueryHandler(display.back_to_main_menu_from_inline, pattern=r'^back_to_main_menu$'), group=0)
    application.add_handler(CallbackQueryHandler(modify_user.renew_user_smart, pattern=r'^renew_'), group=0)
    application.add_handler(CallbackQueryHandler(modify_user.reset_user_traffic, pattern=r'^reset_traffic_'), group=0)
    application.add_handler(CallbackQueryHandler(modify_user.confirm_delete_user, pattern=r'^delete_'), group=0)
    application.add_handler(CallbackQueryHandler(modify_user.do_delete_user, pattern=r'^do_delete_'), group=0)
    application.add_handler(CallbackQueryHandler(modify_user.admin_confirm_delete, pattern=r'^admin_confirm_delete_'), group=0)
    application.add_handler(CallbackQueryHandler(modify_user.admin_reject_delete, pattern=r'^admin_reject_delete_'), group=0)
    application.add_handler(CommandHandler("start", admin_only(display.handle_deep_link_details), filters=filters.Regex(r'details_')), group=0)