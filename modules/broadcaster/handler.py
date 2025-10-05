# FILE: modules/broadcaster/handler.py (REVISED WITH block=True)

from telegram.ext import Application, CommandHandler, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from shared.auth import admin_only, admin_only_conv
from shared.translator import _
from .actions import main as actions
from .actions import forwarder

def register(application: Application) -> None:
    """Registers all handlers for the broadcaster module."""

    message_builder_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f'^{_("keyboards.broadcaster_menu.send_custom_all")}$'), admin_only_conv(actions.start_message_builder)),
            MessageHandler(filters.Regex(f'^{_("keyboards.broadcaster_menu.send_custom_single")}$'), admin_only_conv(actions.start_message_builder)),
        ],
        states={
            actions.BUILDER_MENU: [
                CallbackQueryHandler(actions.prompt_for_content, pattern='^builder_edit_content$'),
                CallbackQueryHandler(actions.add_button_row, pattern='^builder_add_button_row$'),
                CallbackQueryHandler(actions.add_button_to_last_row, pattern='^builder_add_to_last_row$'),
                CallbackQueryHandler(actions.delete_last_button, pattern='^builder_delete_last$'),
                CallbackQueryHandler(actions.show_preview, pattern='^builder_preview$'),
            ],
            actions.AWAITING_CONTENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, actions.process_content),
                MessageHandler(filters.PHOTO, actions.process_content),
                CallbackQueryHandler(actions.back_to_builder_menu, pattern='^builder_back_to_menu$'),
            ],
            actions.AWAITING_BUTTON_TYPE: [
                CallbackQueryHandler(actions.prompt_for_button_url, pattern='^btn_type_url$'),
                CallbackQueryHandler(actions.prompt_for_deeplink_target, pattern='^btn_type_deeplink$'),
                CallbackQueryHandler(actions.back_to_builder_menu, pattern='^builder_back_to_menu$'),
            ],
            actions.AWAITING_BUTTON_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, actions.process_button_target)],
            actions.AWAITING_BUTTON_TARGET_MENU: [
                CallbackQueryHandler(actions.process_button_target, pattern='^(customer_|shop_)'), 
                CallbackQueryHandler(actions.back_to_builder_menu, pattern='^builder_back_to_btn_type$')
            ],
            actions.AWAITING_BUTTON_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, actions.process_button_text_and_add)],
            actions.AWAITING_PREVIEW_CONFIRMATION: [
                CallbackQueryHandler(actions.prompt_for_target_type, pattern='^preview_confirm$'),
                CallbackQueryHandler(actions.back_to_builder_menu, pattern='^builder_back_to_menu$'),
            ],
            actions.AWAITING_SINGLE_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, actions.process_single_user_send)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f'^{_("keyboards.broadcaster_menu.cancel_and_back")}$'), actions.cancel_builder),
            CommandHandler('cancel', actions.cancel_builder),
        ],
        allow_reentry=True,
        # (✨ FIX) Add block=True to prevent other handlers from firing during this conversation.
        block=True 
    )
    
    forwarder_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f'^{_("keyboards.broadcaster_menu.send_forward_all")}$'), admin_only_conv(forwarder.start_forward_broadcast))],
        states={
            forwarder.AWAITING_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.Regex(f'^{_("keyboards.broadcaster_menu.cancel_and_back")}$'), forwarder.ask_for_confirmation)],
            forwarder.AWAITING_CONFIRMATION: [
                CallbackQueryHandler(forwarder.schedule_forward_job, pattern='^forward_confirm$'),
                CallbackQueryHandler(forwarder.cancel_forwarder, pattern='^forward_cancel$')
            ]
        },
        fallbacks=[
            MessageHandler(filters.Regex(f'^{_("keyboards.broadcaster_menu.cancel_and_back")}$'), forwarder.cancel_forwarder),
            CommandHandler('cancel', forwarder.cancel_forwarder)
        ],
        allow_reentry=True,
        # (✨ FIX) Add block=True here as well for consistency and safety.
        block=True 
    )
    
    # Register all handlers for the module
    application.add_handler(
        MessageHandler(filters.Regex(f'^{_("keyboards.admin_main_menu.send_message")}$'), admin_only(actions.show_broadcast_menu)),
        group=0
    )
    application.add_handler(message_builder_conv, group=0)
    application.add_handler(forwarder_conv, group=0)