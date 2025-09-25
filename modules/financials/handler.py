# FILE: modules/financials/handler.py (REFACTORED AND FINAL VERSION)

import logging
from telegram.ext import (
    Application, CallbackQueryHandler, MessageHandler, 
    filters, ConversationHandler
)

# =============================================================================
#  IMPORTS: Only actions related to ADMIN FINANCIAL SETTINGS are imported.
#  Payment processing imports have been MOVED to the 'payment' module.
# =============================================================================
from .actions.settings import (
    card_settings_conv,
    plan_name_settings_conv,
    show_financial_menu,
    show_payment_methods_menu,
    show_plan_management_menu,
    back_to_main_settings_menu
)
from .actions import (
    unlimited_plans_admin, 
    volumetric_plans_admin, 
    wallet_admin, 
    balance_management
)
from shared.callbacks import show_coming_soon
from modules.auth import ADMIN_CONV_FALLBACKS

LOGGER = logging.getLogger(__name__)


def register(application: Application):
    """
    Registers handlers for the ADMIN financial settings panel.
    NOTE: All payment processing handlers (approve/reject/pay) are now in the 'payment' module.
    """
    LOGGER.info("Registering financials settings module handlers...")
    
    # --- Extend Conversation Handlers with Shared Fallbacks for robustness ---
    card_settings_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    plan_name_settings_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    unlimited_plans_admin.add_unlimited_plan_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    volumetric_plans_admin.edit_base_price_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    volumetric_plans_admin.add_tier_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    volumetric_plans_admin.edit_tier_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    wallet_admin.edit_amounts_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)

    balance_management_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(balance_management.start_balance_management, pattern='^admin_manage_balance$')],
        states={
            balance_management.GET_USER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_management.process_user_id),
                CallbackQueryHandler(balance_management.cancel_management, pattern=r'^cancel_balance_management$')
            ],
            balance_management.SHOW_USER_BALANCE: [
                CallbackQueryHandler(balance_management.cancel_management, pattern=r'^cancel_balance_management$'),
                CallbackQueryHandler(balance_management.prompt_for_amount, pattern=r'^balance_')
            ],
            balance_management.GET_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_management.process_amount),
                CallbackQueryHandler(balance_management.show_user_balance_menu, pattern=r'^cancel_amount_entry$')
            ],
        },
        fallbacks=[
            CallbackQueryHandler(balance_management.cancel_management, pattern=r'^cancel_balance_management$'),
            *ADMIN_CONV_FALLBACKS
        ]
    )

    # --- Register ALL Conversation Handlers related to settings ---
    application.add_handler(card_settings_conv)
    application.add_handler(plan_name_settings_conv)
    application.add_handler(unlimited_plans_admin.add_unlimited_plan_conv)
    application.add_handler(volumetric_plans_admin.edit_base_price_conv)
    application.add_handler(volumetric_plans_admin.add_tier_conv)
    application.add_handler(volumetric_plans_admin.edit_tier_conv)
    application.add_handler(wallet_admin.edit_amounts_conv)
    application.add_handler(balance_management_conv)

    # --- Register all other standalone handlers for this module ---
    standalone_handlers = [
        # Main Menu & Navigation
        MessageHandler(filters.Regex('^💰 تنظیمات مالی$'), show_financial_menu),
        CallbackQueryHandler(show_payment_methods_menu, pattern=r'^show_payment_methods$'),
        CallbackQueryHandler(show_plan_management_menu, pattern=r'^show_plan_management$'),
        CallbackQueryHandler(wallet_admin.show_wallet_settings_menu, pattern=r'^admin_wallet_settings$'),
        CallbackQueryHandler(show_financial_menu, pattern=r'^back_to_financial_settings$'),
        CallbackQueryHandler(back_to_main_settings_menu, pattern=r'^back_to_main_settings$'),
        CallbackQueryHandler(show_plan_management_menu, pattern=r'^back_to_plan_management$'),

        # Unlimited Plan Management Callbacks
        CallbackQueryHandler(unlimited_plans_admin.manage_unlimited_plans_menu, pattern=r'^admin_manage_unlimited$'),
        CallbackQueryHandler(unlimited_plans_admin.confirm_delete_plan, pattern=r'^unlimplan_delete_'),
        CallbackQueryHandler(unlimited_plans_admin.execute_delete_plan, pattern=r'^unlimplan_do_delete_'),
        CallbackQueryHandler(unlimited_plans_admin.toggle_plan_status, pattern=r'^unlimplan_toggle_'),
        
        # Volumetric Plan Management Callbacks
        CallbackQueryHandler(volumetric_plans_admin.manage_volumetric_plans_menu, pattern=r'^admin_manage_volumetric$'),
        CallbackQueryHandler(volumetric_plans_admin.confirm_delete_tier, pattern=r'^vol_delete_tier_'),
        CallbackQueryHandler(volumetric_plans_admin.execute_delete_tier, pattern=r'^vol_do_delete_tier_'),

        # Placeholder
        CallbackQueryHandler(show_coming_soon, pattern=r'^coming_soon$'),
    ]
    
    application.add_handlers(standalone_handlers)
    
    LOGGER.info("Financials settings module handlers registered successfully.")