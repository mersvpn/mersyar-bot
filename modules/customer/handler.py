# FILE: modules/customer/handler.py (CORRECTED FINAL VERSION)

import logging
from telegram.ext import (
    Application, ConversationHandler, MessageHandler,
    CallbackQueryHandler, filters, CommandHandler
)

from .actions import (
    purchase, renewal, service, panel, guide, wallet,
    receipt as receipt_actions,
    custom_purchase as custom_purchase_actions,
    unlimited_purchase as unlimited_purchase_actions,
    charge as charge_actions,
    test_account as test_account_actions
)
from .actions import purchase, renewal, service, panel, guide, wallet

from modules.general.actions import end_conversation_and_show_menu, end_conv_and_reroute, start
from config import config

LOGGER = logging.getLogger(__name__)

MAIN_MENU_REGEX = r'^(🛍️فــــــــــروشـــــــــــگاه|📊ســــــــرویس‌های من|📱 راهــــــــــنمای اتصال|🔙 بازگشت به منوی اصلی)$'
IGNORE_MAIN_MENU_FILTER = filters.TEXT & ~filters.COMMAND & ~filters.Regex(MAIN_MENU_REGEX)

# Define states for the wallet conversation
DISPLAY_PANEL = 0
charge_actions.DISPLAY_PANEL = DISPLAY_PANEL # Share state with charge module

def register(application: Application):
    LOGGER.info("Registering UNIFIED customer module handlers...")
    
    unified_fallback = [
        MessageHandler(filters.Regex(MAIN_MENU_REGEX), end_conv_and_reroute),
        CommandHandler('cancel', end_conversation_and_show_menu)
    ]

    my_service_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📊ســــــــرویس‌های من$'), service.handle_my_service)],
        states={
            service.CHOOSE_SERVICE: [
                CallbackQueryHandler(service.choose_service, pattern=r'^select_service_'),
                CallbackQueryHandler(service.handle_service_page_change, pattern=r'^page_(fwd|back)_')
            ],
            service.DISPLAY_SERVICE: [
                CallbackQueryHandler(service.choose_service, pattern=r'^select_service_'),
                CallbackQueryHandler(renewal.handle_renewal_request, pattern=r'^customer_renew_request_'),
                CallbackQueryHandler(service.confirm_reset_subscription, pattern=r'^customer_reset_sub_'),
                CallbackQueryHandler(service.request_delete_service, pattern=r'^request_delete_'),
                CallbackQueryHandler(service.start_data_purchase, pattern=r'^purchase_data_'),
                CallbackQueryHandler(service.toggle_auto_renew, pattern=r'^toggle_autorenew_')
                
            ],
            service.CONFIRM_RESET_SUB: [
                CallbackQueryHandler(service.execute_reset_subscription, pattern=r'^do_reset_sub_'),
                CallbackQueryHandler(service.choose_service, pattern=r'^select_service_')
            ],
            service.CONFIRM_DELETE: [
                CallbackQueryHandler(service.confirm_delete_request, pattern=r'^confirm_delete_'),
                CallbackQueryHandler(service.choose_service, pattern=r'^select_service_')
            ],
            service.PROMPT_FOR_DATA_AMOUNT: [
                MessageHandler(IGNORE_MAIN_MENU_FILTER, service.calculate_price_and_confirm)
            ],
            service.CONFIRM_DATA_PURCHASE: [
                CallbackQueryHandler(service.generate_data_purchase_invoice, pattern=r'^confirm_data_purchase_final$'),
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
            unlimited_purchase_actions.CONFIRM_UNLIMITED_PLAN: [CallbackQueryHandler(unlimited_purchase_actions.generate_unlimited_invoice, pattern=r'^unlim_confirm_final$')],
        },
        fallbacks=[
            CallbackQueryHandler(unlimited_purchase_actions.cancel_unlimited_purchase, pattern=f'^{unlimited_purchase_actions.CANCEL_CALLBACK_DATA}$'),
            *unified_fallback
        ],
        conversation_timeout=600,
        per_message=False
    )
    
    wallet_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^💵 موجودی \+ شارژ حساب$'), wallet.show_wallet_panel)],
        states={
            DISPLAY_PANEL: [
                CallbackQueryHandler(charge_actions.start_charge_process, pattern=f'^{wallet.CALLBACK_CHARGE_WALLET}$')
            ],
            charge_actions.CHOOSE_AMOUNT: [
                CallbackQueryHandler(charge_actions.handle_predefined_amount, pattern=f'^{charge_actions.CALLBACK_PREFIX_AMOUNT}'),
                CallbackQueryHandler(charge_actions.prompt_for_custom_amount, pattern=f'^{charge_actions.CALLBACK_CUSTOM_AMOUNT}$')
            ],
            charge_actions.GET_CUSTOM_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, charge_actions.handle_custom_amount)
            ],
            charge_actions.CONFIRM_CHARGE: [
                CallbackQueryHandler(charge_actions.generate_charge_invoice, pattern=f'^{charge_actions.CALLBACK_CONFIRM_FINAL}$')
            ]
        },
        fallbacks=[
            CallbackQueryHandler(charge_actions.back_to_wallet_panel, pattern=f'^{charge_actions.CALLBACK_CANCEL_CHARGE}$'),
            CallbackQueryHandler(wallet.close_wallet_panel, pattern=f'^{wallet.CALLBACK_WALLET_CLOSE}$'),
            *unified_fallback
        ],
        conversation_timeout=600,
        per_message=False
    )
    
    application.add_handler(my_service_conv, group=1)
    application.add_handler(manual_purchase_conv, group=1)
    application.add_handler(receipt_conv, group=1)
    application.add_handler(custom_purchase_conv, group=1)
    application.add_handler(unlimited_purchase_conv, group=1)
    application.add_handler(wallet_conv, group=1)

    application.add_handler(MessageHandler(filters.Regex(r'^🛍️فــــــــــروشـــــــــــگاه$'), panel.show_customer_panel), group=1)
    application.add_handler(MessageHandler(filters.Regex(r'^📱 راهــــــــــنمای اتصال$'), guide.show_guides_to_customer), group=1)
    application.add_handler(MessageHandler(filters.Regex(r'^🔙 بازگشت به منوی اصلی$'), start), group=1)
    application.add_handler(CallbackQueryHandler(renewal.handle_renewal_request, pattern=r'^customer_renew_request_'), group=1)
    #if config.SUPPORT_USERNAME:
    application.add_handler(MessageHandler(filters.Regex(r'^💬 پشتیبـــانی$'), purchase.handle_support_button), group=1)

    # Handler for Test Account button
    application.add_handler(MessageHandler(filters.Regex(r'^⏳ اکانــت تســت$'), test_account_actions.handle_test_account_request), group=1)

    # Handlers for Guide navigation
    application.add_handler(CallbackQueryHandler(guide.send_guide_content_to_customer, pattern=r'^customer_show_guide_'), group=1)
    application.add_handler(CallbackQueryHandler(guide.show_guides_to_customer, pattern=r'^customer_back_to_guides$'), group=1)
    application.add_handler(CallbackQueryHandler(guide.close_guide_menu, pattern=r'^close_guide_menu$'), group=1)
    