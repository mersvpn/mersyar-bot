# FILE: modules/user_info\handler.py

from telegram.ext import Application, ConversationHandler, MessageHandler, CallbackQueryHandler, filters
from shared.auth import admin_only_conv
from shared.translator import _

from .actions.display import (
    AWAIT_USER_ID, MAIN_MENU, EDIT_NOTE,
    start_customer_info, process_user_id, show_comprehensive_info,
    show_services, show_note_manager,
    prompt_for_note, save_note, refresh_data, close_menu
)

def register(application: Application) -> None:
    customer_info_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(f"^{_('keyboards.admin_main_menu.customer_info')}$") & filters.TEXT,

                admin_only_conv(start_customer_info)
            )
        ],
        states={
            AWAIT_USER_ID: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filters.Regex(f"^{_('user_info.menu.back_to_main')}$"),
                    admin_only_conv(process_user_id)
                ),
                MessageHandler(
                    filters.Regex(f"^{_('user_info.menu.back_to_main')}$"),
                    admin_only_conv(close_menu)
                )
            ],
            MAIN_MENU: [
                # --- KEY CHANGE: "user_profile" button now calls the comprehensive function ---
                MessageHandler(
                    filters.Regex(f"^{_('user_info.menu.user_profile')}$"),
                    admin_only_conv(show_comprehensive_info) # <--- Calls the new merged function
                ),
                # The "financial_info" handler is completely removed.
                MessageHandler(
                    filters.Regex(f"^{_('user_info.menu.services')}$"),
                    admin_only_conv(show_services)
                ),
                MessageHandler(
                    filters.Regex(f"^{_('user_info.menu.note_management')}$"),
                    admin_only_conv(show_note_manager)
                ),
                MessageHandler(
                    filters.Regex(f"^{_('user_info.menu.back_to_main')}$"),
                    admin_only_conv(close_menu)
                ),
                # CallbackQueryHandlers remain unchanged
                CallbackQueryHandler(
                    admin_only_conv(refresh_data),
                    pattern="^ui:refresh:"
                ),
                CallbackQueryHandler(
                    admin_only_conv(close_menu),
                    pattern="^ui:close$"
                ),
                CallbackQueryHandler(
                    admin_only_conv(prompt_for_note),
                    pattern="^ui:edit_note:"
                ),
                CallbackQueryHandler(
                    admin_only_conv(prompt_for_note),
                    pattern="^ui:delete_note:"
                )
            
            ],
            EDIT_NOTE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_only_conv(save_note)
                )
            ]
        },
        fallbacks=[
            MessageHandler(
                filters.Regex(f"^{_('user_info.menu.back_to_main')}$"),
                admin_only_conv(close_menu)
            )
        ],
        name="customer_info_conversation",
        persistent=False,
        allow_reentry=True
    )
    
    application.add_handler(customer_info_conv)
