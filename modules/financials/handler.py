# FILE: financials/handler.py (FINAL VERSION - HANDLER DEFINITIONS)

import logging
from telegram.ext import (
    Application, CallbackQueryHandler, MessageHandler, 
    filters, ConversationHandler
)

from .actions.settings import (
    card_settings_conv,
    plan_name_settings_conv,
    show_financial_menu,
    show_payment_methods_menu,
    show_plan_management_menu,
    back_to_main_settings_menu
)
from .actions.payment import (
    payment_request_conv,
    handle_payment_back_button,
    approve_payment,
    reject_payment,
    confirm_manual_payment,
    pay_with_wallet
)
from .actions import (
    unlimited_plans_admin, 
    volumetric_plans_admin, 
    wallet_admin, 
    balance_management,
    payment
)
from shared.callbacks import show_coming_soon
from modules.auth import ADMIN_CONV_FALLBACKS

LOGGER = logging.getLogger(__name__)


def register(application: Application):
    """Registers all handlers for the financials module."""
    LOGGER.info("Registering financials module handlers...")
    
    # --- Define Conversations with Shared Fallbacks ---
    card_settings_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    payment_request_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    plan_name_settings_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    unlimited_plans_admin.add_unlimited_plan_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    volumetric_plans_admin.edit_base_price_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    volumetric_plans_admin.add_tier_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    volumetric_plans_admin.edit_tier_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    wallet_admin.edit_amounts_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)

    balance_management_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(balance_management.start_balance_management, pattern='^admin_manage_balance$')],
        states={
            balance_management.GET_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, balance_management.process_user_id)],
            balance_management.SHOW_USER_BALANCE: [
                CallbackQueryHandler(balance_management.cancel_management, pattern=r'^balance_back$'),
                CallbackQueryHandler(balance_management.prompt_for_amount, pattern=r'^balance_')
            ],
            balance_management.GET_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_management.process_amount),
                CallbackQueryHandler(balance_management.show_user_balance_menu, pattern=r'^cancel_amount_entry$')
            ],
        },
        fallbacks=[*ADMIN_CONV_FALLBACKS]
    )

    # =============================================================================
    #  1. Admin Handlers (Group 0)
    # =============================================================================

    # --- Main Menu & Navigation ---
    application.add_handler(MessageHandler(filters.Regex('^💰 تنظیمات مالی$'), show_financial_menu), group=0)
    application.add_handler(CallbackQueryHandler(show_payment_methods_menu, pattern=r'^show_payment_methods$'), group=0)
    application.add_handler(CallbackQueryHandler(show_plan_management_menu, pattern=r'^show_plan_management$'), group=0)
    application.add_handler(CallbackQueryHandler(wallet_admin.show_wallet_settings_menu, pattern=r'^admin_wallet_settings$'), group=0)
    application.add_handler(CallbackQueryHandler(show_financial_menu, pattern=r'^back_to_financial_settings$'), group=0)
    application.add_handler(CallbackQueryHandler(back_to_main_settings_menu, pattern=r'^back_to_main_settings$'), group=0)

    # --- Register ALL Conversations ---
    application.add_handler(card_settings_conv, group=0)
    application.add_handler(payment_request_conv, group=0)
    application.add_handler(plan_name_settings_conv, group=0)
    application.add_handler(unlimited_plans_admin.add_unlimited_plan_conv, group=0)
    application.add_handler(volumetric_plans_admin.edit_base_price_conv, group=0)
    application.add_handler(volumetric_plans_admin.add_tier_conv, group=0)
    application.add_handler(volumetric_plans_admin.edit_tier_conv, group=0)
    application.add_handler(wallet_admin.edit_amounts_conv, group=0)
    application.add_handler(balance_management_conv, group=0)

    # --- Plan Management Handlers (Standalone Callbacks) ---
    application.add_handler(CallbackQueryHandler(unlimited_plans_admin.manage_unlimited_plans_menu, pattern=r'^admin_manage_unlimited$'), group=0)
    application.add_handler(CallbackQueryHandler(unlimited_plans_admin.confirm_delete_plan, pattern=r'^unlimplan_delete_'), group=0)
    application.add_handler(CallbackQueryHandler(unlimited_plans_admin.execute_delete_plan, pattern=r'^unlimplan_do_delete_'), group=0)
    application.add_handler(CallbackQueryHandler(unlimited_plans_admin.toggle_plan_status, pattern=r'^unlimplan_toggle_'), group=0)
    
    application.add_handler(CallbackQueryHandler(volumetric_plans_admin.manage_volumetric_plans_menu, pattern=r'^admin_manage_volumetric$'), group=0)
    application.add_handler(CallbackQueryHandler(volumetric_plans_admin.confirm_delete_tier, pattern=r'^vol_delete_tier_'), group=0)
    application.add_handler(CallbackQueryHandler(volumetric_plans_admin.execute_delete_tier, pattern=r'^vol_do_delete_tier_'), group=0)

    # --- Receipt Approval/Rejection Handlers ---
    application.add_handler(CallbackQueryHandler(approve_payment, pattern=r'^approve_receipt_'), group=0)
    application.add_handler(CallbackQueryHandler(confirm_manual_payment, pattern=r'^confirm_manual_receipt_'), group=0)
    application.add_handler(CallbackQueryHandler(payment.approve_data_top_up, pattern=r'^approve_data_top_up_'), group=0)
    application.add_handler(CallbackQueryHandler(reject_payment, pattern=r'^reject_receipt_'), group=0)

    application.add_handler(CallbackQueryHandler(show_coming_soon, pattern=r'^coming_soon$'), group=0)
    
    # =============================================================================
    #  2. Customer Handlers (Group 1)
    # =============================================================================
    application.add_handler(CallbackQueryHandler(handle_payment_back_button, pattern=r'^payment_back_to_menu$'), group=1)
    application.add_handler(CallbackQueryHandler(pay_with_wallet, pattern=r'^wallet_pay_'), group=1)
    
    LOGGER.info("Financials module handlers registered successfully.")