# FILE: modules/customer/handler.py
# (نسخه نهایی و کاملاً بازنویسی شده)

# ===== IMPORTS & DEPENDENCIES =====
from telegram.ext import (
    Application, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, CommandHandler
)

# --- Local Imports ---
# Import all necessary action modules
from .actions import purchase, renewal, service, panel, receipt
from modules.general.actions import start as start_action # For fallbacks

# ===== REGISTRATION =====
def register(application: Application):
    """Registers all handlers for the customer module."""

    # A fallback to the main menu for all customer conversations
    customer_fallbacks = [CommandHandler('start', start_action)]

    # --- 1. Conversation Handler for 'My Service' (No changes here) ---
    my_service_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📊 سرویس من$'), service.handle_my_service)],
        states={
            service.CHOOSE_SERVICE: [
                CallbackQueryHandler(service.choose_service, pattern=r'^select_service_'),
                CallbackQueryHandler(service.back_to_main_menu_customer, pattern=r'^customer_back_to_main_menu$')
            ],
            service.DISPLAY_SERVICE: [
                CallbackQueryHandler(service.back_to_main_menu_customer, pattern=r'^customer_back_to_main_menu$'),
                CallbackQueryHandler(service.confirm_reset_subscription, pattern=r'^customer_reset_sub_'),
                CallbackQueryHandler(service.request_delete_service, pattern=r'^request_delete_')
            ],
            service.CONFIRM_RESET_SUB: [
                CallbackQueryHandler(service.execute_reset_subscription, pattern=r'^do_reset_sub_'),
                CallbackQueryHandler(service.choose_service, pattern=r'^select_service_')
            ],
            service.CONFIRM_DELETE: [
                CallbackQueryHandler(service.confirm_delete_request, pattern=r'^confirm_delete_'),
                CallbackQueryHandler(service.choose_service, pattern=r'^select_service_')
            ]
        },
        fallbacks=customer_fallbacks,
        conversation_timeout=300
    )

    # --- 2. Conversation Handler for the Purchase Flow (Now starts from the panel) ---
    purchase_conv = ConversationHandler(
        entry_points=[
            # The entry point is now a CallbackQuery from the customer panel
            CallbackQueryHandler(purchase.start_purchase, pattern='^start_purchase_flow$')
        ],
        states={
            purchase.CONFIRM_PURCHASE: [
                CallbackQueryHandler(purchase.confirm_purchase, pattern='^confirm_purchase_request$'),
                CallbackQueryHandler(purchase.cancel_purchase, pattern='^cancel_purchase_request$')
            ]
        },
        fallbacks=customer_fallbacks,
        conversation_timeout=300
    )
    
    # --- 3. NEW: Conversation Handler for Receipt Upload (Imported from receipt.py) ---
    # The `receipt_conv` is already defined in the receipt.py file, we just need to register it.
    
    # --- 4. Register all handlers with group 1 (customer priority) ---
    application.add_handler(my_service_conv, group=1)
    application.add_handler(purchase_conv, group=1)
    application.add_handler(receipt.receipt_conv, group=1) # <-- Registering the new receipt conversation

    # --- 5. Standalone Handlers (not part of conversations) ---

    # NEW: Handler for the main "Customer Panel" button
    application.add_handler(MessageHandler(filters.Regex('^🛍️ پنل خرید و پرداخت$'), panel.show_customer_panel), group=1)
    
    # NEW: Handler to close the customer panel
    application.add_handler(CallbackQueryHandler(panel.close_customer_panel, pattern='^close_customer_panel$'), group=1)

    # Support button handler
    from config import config
    if config.SUPPORT_USERNAME:
        application.add_handler(MessageHandler(filters.Regex('^💬 پشتیبانی$'), purchase.handle_support_button), group=1)

    # Handlers for renewal/non-renewal buttons from reminder messages
    application.add_handler(CallbackQueryHandler(renewal.handle_renewal_request, pattern=r'^customer_renew_request_'), group=1)
    application.add_handler(CallbackQueryHandler(renewal.handle_do_not_renew, pattern=r'^customer_do_not_renew_'), group=1)

    # NOTE: The old generic photo handler has been removed, as the new `receipt_conv` is much safer and more specific.