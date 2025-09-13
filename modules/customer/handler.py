# FILE: modules/customer/handler.py (FINAL VERSION WITH BACK BUTTON FIX)

import logging
from telegram.ext import (
    Application, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, CommandHandler
)

# Import action files directly
from .actions import purchase, renewal, service, panel, guide
from .actions import receipt as receipt_actions
from .actions import custom_purchase as custom_purchase_actions
from .actions import unlimited_purchase as unlimited_purchase_actions

from modules.general.actions import end_conversation_and_show_menu, end_conv_and_reroute, start
from config import config

LOGGER = logging.getLogger(__name__)

# --- A Regex to match ALL main menu buttons that can interrupt a conversation ---
MAIN_MENU_REGEX = r'^(🛍️فــــــــــروشـــــــــــگاه|📊ســـــــــــرویس‌های من|📱 راهــــــــــنمای اتصال|🔙 بازگشت به منوی اصلی)$'

# --- A filter to IGNORE all main menu buttons, for use in states that expect user input ---
IGNORE_MAIN_MENU_FILTER = filters.TEXT & ~filters.COMMAND & ~filters.Regex(MAIN_MENU_REGEX)


def register(application: Application):
    LOGGER.info("Registering UNIFIED customer module handlers...")
    
    unified_fallback = [
        MessageHandler(filters.Regex(MAIN_MENU_REGEX), end_conv_and_reroute),
        CommandHandler('cancel', end_conversation_and_show_menu)
    ]

    # ... (All ConversationHandler definitions remain exactly the same as the last version) ...
    my_service_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📊ســـــــــــرویس‌های من$'), service.handle_my_service)],
        states={
            service.CHOOSE_SERVICE: [
                CallbackQueryHandler(service.choose_service, pattern=r'^select_service_'),
                CallbackQueryHandler(service.handle_service_page_change, pattern=r'^page_(fwd|back)_')
            ],
            service.DISPLAY_SERVICE: [
                 CallbackQueryHandler(service.choose_service, pattern=r'^select_service_'), # Allows returning to details
                CallbackQueryHandler(renewal.handle_renewal_request, pattern=r'^customer_renew_request_'),
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
        fallbacks=[
            CallbackQueryHandler(service.back_to_main_menu_customer, pattern=r'^customer_back_to_main_menu$'),
            *unified_fallback
        ],
        conversation_timeout=600,
        per_message=False
    )
    
    manual_purchase_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Text("👨‍💻 ساخت اشتراک توسط پشتیبانی"), purchase.start_purchase)],
        states={
            purchase.CONFIRM_PURCHASE: [
                CallbackQueryHandler(purchase.confirm_purchase, pattern='^confirm_purchase_request$'),
                CallbackQueryHandler(purchase.back_to_shop_menu, pattern='^back_to_shop_menu$')
            ]
        },
        fallbacks=unified_fallback,
        conversation_timeout=300,
        per_message=False
    )
    
    receipt_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^🧾 ارسال رسید پرداخت$'), receipt_actions.start_receipt_from_menu),
            CallbackQueryHandler(receipt_actions.start_receipt_from_invoice, pattern='^customer_send_receipt$')
        ],
        states={
            receipt_actions.CHOOSE_INVOICE: [CallbackQueryHandler(receipt_actions.select_invoice_for_receipt, pattern='^select_invoice_')],
            receipt_actions.GET_RECEIPT_PHOTO: [
                MessageHandler(filters.PHOTO & ~filters.COMMAND, receipt_actions.handle_receipt_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receipt_actions.warn_for_photo)
            ]
        },
        fallbacks=[
            CallbackQueryHandler(receipt_actions.cancel_receipt_upload, pattern='^cancel_receipt_upload$'),
            *unified_fallback
        ],
        conversation_timeout=600,
        per_message=False
    )

    custom_purchase_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^♻️ اشتراک با حجم دلخواه$'), custom_purchase_actions.start_custom_purchase)],
        states={
            custom_purchase_actions.ASK_USERNAME: [MessageHandler(IGNORE_MAIN_MENU_FILTER, custom_purchase_actions.get_username_and_ask_volume)],
            custom_purchase_actions.ASK_VOLUME: [MessageHandler(IGNORE_MAIN_MENU_FILTER, custom_purchase_actions.get_volume_and_ask_for_duration)],
            custom_purchase_actions.ASK_DURATION: [MessageHandler(IGNORE_MAIN_MENU_FILTER, custom_purchase_actions.get_duration_and_confirm)],
            custom_purchase_actions.CONFIRM_PLAN: [CallbackQueryHandler(custom_purchase_actions.generate_invoice, pattern='^confirm_custom_plan$')],
        },
        fallbacks=[
            CallbackQueryHandler(custom_purchase_actions.cancel_custom_purchase, pattern=f'^{custom_purchase_actions.CANCEL_CALLBACK_DATA}$'),
            *unified_fallback
        ],
        conversation_timeout=600,
        per_message=False
    )

    unlimited_purchase_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^💎 اشتراک با حجم نامحدود$'), unlimited_purchase_actions.start_unlimited_purchase)],
        states={
            unlimited_purchase_actions.ASK_USERNAME: [MessageHandler(IGNORE_MAIN_MENU_FILTER, unlimited_purchase_actions.get_username_and_ask_plan)],
            unlimited_purchase_actions.CHOOSE_PLAN: [CallbackQueryHandler(unlimited_purchase_actions.select_plan_and_confirm, pattern=r'^unlim_select_')],
            unlimited_purchase_actions.CONFIRM_UNLIMITED_PLAN: [CallbackQueryHandler(unlimited_purchase_actions.generate_unlimited_invoice, pattern='^unlim_confirm_final$')],
        },
        fallbacks=[
            CallbackQueryHandler(unlimited_purchase_actions.cancel_unlimited_purchase, pattern=f'^{unlimited_purchase_actions.CANCEL_CALLBACK_DATA}$'),
            *unified_fallback
        ],
        conversation_timeout=600,
        per_message=False
    )

    # --- Registration of ALL Handlers for this module ---

    # Conversations
    application.add_handler(my_service_conv, group=1)
    application.add_handler(manual_purchase_conv, group=1)
    application.add_handler(receipt_conv, group=1)
    application.add_handler(custom_purchase_conv, group=1)
    application.add_handler(unlimited_purchase_conv, group=1)

    # Standalone Handlers
    application.add_handler(MessageHandler(filters.Regex('^🛍️فــــــــــروشـــــــــــگاه$'), panel.show_customer_panel), group=1)
    application.add_handler(MessageHandler(filters.Regex('^📱 راهــــــــــنمای اتصال$'), guide.show_guides_to_customer), group=1)
    
    # V V V NEW HANDLER ADDED HERE V V V
    # This handler catches the 'Back to Main Menu' button when NO conversation is active (e.g., from the shop menu).
    application.add_handler(MessageHandler(filters.Regex('^🔙 بازگشت به منوی اصلی$'), start), group=1)
    # ^ ^ ^ NEW HANDLER ADDED HERE ^ ^ ^

    if config.SUPPORT_USERNAME:
        application.add_handler(MessageHandler(filters.Regex('^💬 پشتیبانی$'), purchase.handle_support_button), group=1)

    # Guide-specific callbacks
    application.add_handler(CallbackQueryHandler(guide.send_guide_content_to_customer, pattern=r'^customer_show_guide_'), group=1)
    application.add_handler(CallbackQueryHandler(guide.show_guides_to_customer, pattern=r'^customer_back_to_guides$'), group=1)
    application.add_handler(CallbackQueryHandler(guide.close_guide_menu, pattern=r'^close_guide_menu$'), group=1)
    application.add_handler(CallbackQueryHandler(renewal.handle_renewal_request, pattern=r'^customer_renew_request_'), group=1)