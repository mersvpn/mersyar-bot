# FILE: modules/guides/handler.py (نسخه نهایی با اصلاح بازگشت از پیش‌نمایش)

from telegram.ext import (
    Application, ConversationHandler, CallbackQueryHandler,
    MessageHandler, filters, CommandHandler
)
from modules.auth import admin_only_conv
from .actions import (
    LIST_GUIDES, GUIDE_MENU, CONFIRM_DELETE, BUTTON_MENU, 
    EDIT_KEY, EDIT_TITLE, EDIT_CONTENT, EDIT_PHOTO, 
    GET_BUTTON_TEXT, GET_BUTTON_URL, SELECT_BUTTON_TO_DELETE,
    start_guide_management,
    show_guide_menu,
    prompt_for_new_guide_key,
    process_new_guide_key,
    prompt_for_edit,
    process_edit_title,
    process_edit_content,
    process_edit_photo,
    show_buttons_menu,
    prompt_for_button_text,
    get_button_text_and_prompt_for_url,
    get_button_url_and_save,
    prompt_to_delete_button,
    do_delete_button,
    view_guide,
    confirm_delete_guide,
    do_delete_guide,
    back_to_main_menu,
)

def register(application: Application) -> None:
    """Registers the redesigned guide management conversation handler."""
    
    guide_management_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^📚 تنظیمات آموزش$'), admin_only_conv(start_guide_management))
        ],
        states={
            LIST_GUIDES: [
                CallbackQueryHandler(show_guide_menu, pattern=r'^guide_manage_'),
                CallbackQueryHandler(prompt_for_new_guide_key, pattern=r'^guide_add_new$'),
            ],
            GUIDE_MENU: [
                CallbackQueryHandler(start_guide_management, pattern=r'^guide_back_to_list$'),
                CallbackQueryHandler(prompt_for_edit, pattern=r'^guide_edit_(title|content|photo)$'),
                CallbackQueryHandler(show_buttons_menu, pattern=r'^guide_edit_buttons$'),
                CallbackQueryHandler(view_guide, pattern=r'^guide_view_'),
                CallbackQueryHandler(confirm_delete_guide, pattern=r'^guide_delete_confirm_'),
                # --- خط جدید برای بازگشت از پیش‌نمایش ---
                CallbackQueryHandler(show_guide_menu, pattern=r'^guide_manage_'),
            ],
            CONFIRM_DELETE: [
                CallbackQueryHandler(do_delete_guide, pattern=r'^guide_delete_do_'),
                CallbackQueryHandler(show_guide_menu, pattern=r'^guide_manage_')
            ],
            BUTTON_MENU: [
                CallbackQueryHandler(show_guide_menu, pattern=r'^guide_manage_'),
                CallbackQueryHandler(prompt_for_button_text, pattern=r'^guide_btn_add$'),
                CallbackQueryHandler(prompt_to_delete_button, pattern=r'^guide_btn_delete_prompt$'),
            ],
            SELECT_BUTTON_TO_DELETE: [
                CallbackQueryHandler(do_delete_button, pattern=r'^guide_btn_delete_do_'),
                CallbackQueryHandler(show_buttons_menu, pattern=r'^guide_edit_buttons$'),
            ],
            EDIT_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_guide_key)],
            EDIT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_edit_title)],
            EDIT_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_edit_content)],
            EDIT_PHOTO: [MessageHandler(filters.PHOTO | filters.Regex('^حذف$'), process_edit_photo)],
            GET_BUTTON_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_button_text_and_prompt_for_url)],
            GET_BUTTON_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_button_url_and_save)],
        },
        fallbacks=[
            CommandHandler('cancel', back_to_main_menu),
            CallbackQueryHandler(back_to_main_menu, pattern=r'^guide_back_to_main$')
        ],
        per_user=True,
        per_chat=True,
        name="guide_management_conversation"
    )
    
    application.add_handler(guide_management_conv)