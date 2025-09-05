# FILE: modules/customer/handler.py (نسخه نهایی با مکالمه خرید پلن نامحدود)

import logging
from telegram.ext import (
    Application, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, CommandHandler
)

# --- MODIFIED: Import the new unlimited_purchase module ---
from .actions import purchase, renewal, service, panel, receipt, guide, custom_purchase, unlimited_purchase
from modules.general.actions import start as start_action

LOGGER = logging.getLogger(__name__)

def register(application: Application):
    LOGGER.info("Registering customer module handlers...")
    customer_fallbacks = [CommandHandler('start', start_action)]

    # --- Conversations (No changes here) ---
    my_service_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📊 سرویس من$'), service.handle_my_service)],
        states={
            service.CHOOSE_SERVICE: [CallbackQueryHandler(service.choose_service, pattern=r'^select_service_')],
            service.DISPLAY_SERVICE: [
                CallbackQueryHandler(renewal.handle_renewal_request, pattern=r'^customer_renew_request_'),
                CallbackQueryHandler(service.confirm_reset_subscription, pattern=r'^customer_reset_sub_'),
                CallbackQueryHandler(service.request_delete_service, pattern=r'^request_delete_'),
            ],
            service.CONFIRM_RESET_SUB: [CallbackQueryHandler(service.execute_reset_subscription, pattern=r'^do_reset_sub_')],
            service.CONFIRM_DELETE: [CallbackQueryHandler(service.confirm_delete_request, pattern=r'^confirm_delete_')]
        },
        fallbacks=[CallbackQueryHandler(service.back_to_main_menu_customer, pattern=r'^customer_back_to_main_menu$')] + customer_fallbacks,
        conversation_timeout=300,
        per_user=True, per_chat=True
    )
    
    manual_purchase_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(purchase.start_purchase, pattern='^customer_manual_purchase$')],
        states={
            purchase.CONFIRM_PURCHASE: [
                CallbackQueryHandler(purchase.confirm_purchase, pattern='^confirm_purchase_request$'),
                CallbackQueryHandler(purchase.cancel_purchase, pattern=r'^cancel_purchase_request$') 
            ]
        },
        fallbacks=[CallbackQueryHandler(panel.show_customer_panel, pattern='^back_to_customer_panel$')] + customer_fallbacks,
        conversation_timeout=300,
        per_user=True, per_chat=True
    )

    # --- Registering Handlers ---
    application.add_handler(my_service_conv, group=1)
    application.add_handler(manual_purchase_conv, group=1)
    application.add_handler(receipt.receipt_conv, group=1)
    application.add_handler(custom_purchase.custom_purchase_conv, group=1)
    # --- NEW: Register the unlimited purchase conversation ---
    application.add_handler(unlimited_purchase.unlimited_purchase_conv, group=1)

    # --- Standalone Handlers for Purchase Panel ---
    application.add_handler(MessageHandler(filters.Regex('^🛍️ پنل خرید و پرداخت$'), panel.show_customer_panel), group=1)
    application.add_handler(CallbackQueryHandler(panel.close_customer_panel, pattern='^close_panel$'), group=1)
    application.add_handler(CallbackQueryHandler(panel.show_plan_type_menu, pattern='^show_plan_type_menu$'), group=1)
    application.add_handler(CallbackQueryHandler(panel.show_customer_panel, pattern='^back_to_purchase_panel$'), group=1)
    
    # --- Other Handlers (No changes here) ---
    from config import config
    if config.SUPPORT_USERNAME:
        application.add_handler(MessageHandler(filters.Regex('^💬 پشتیبانی$'), purchase.handle_support_button), group=1)
    
    application.add_handler(CallbackQueryHandler(renewal.handle_do_not_renew, pattern=r'^customer_do_not_renew_'), group=1)
    application.add_handler(CallbackQueryHandler(guide.send_guide_content_to_customer, pattern=r'^customer_show_guide_'), group=1)
    application.add_handler(CallbackQueryHandler(guide.show_guides_to_customer, pattern=r'^customer_back_to_guides$'), group=1)
    application.add_handler(CallbackQueryHandler(guide.close_guide_menu, pattern=r'^close_guide_menu$'), group=1)
    application.add_handler(CallbackQueryHandler(renewal.handle_renewal_request, pattern=r'^customer_renew_request_'), group=1)
    LOGGER.info("Customer module handlers registered successfully.")