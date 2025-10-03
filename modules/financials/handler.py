# FILE: modules/financials/handler.py

import logging
from telegram.ext import (
    Application, CallbackQueryHandler, MessageHandler, 
    filters, ConversationHandler,CommandHandler
)
from shared.translator import _ # <-- Import _ for regex matching
# ... (بقیه import های شما) ...
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
    balance_management,gift
)
from shared.callbacks import show_coming_soon, main_menu_fallback, end_conversation_and_show_menu

from shared.auth import ADMIN_CONV_FALLBACKS

LOGGER = logging.getLogger(__name__)

def register(application: Application):
    """
    Registers handlers for the ADMIN financial settings panel.
    """
    LOGGER.info("Registering financials settings module handlers...")
    
    # --- Extend other Conversation Handlers with Shared Fallbacks ---
    card_settings_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    plan_name_settings_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    unlimited_plans_admin.add_unlimited_plan_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    volumetric_plans_admin.edit_base_price_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    volumetric_plans_admin.add_tier_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    volumetric_plans_admin.edit_tier_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)
    wallet_admin.edit_amounts_conv.fallbacks.extend(ADMIN_CONV_FALLBACKS)

    # --- ✨ REVISED AND STABILIZED CONVERSATION HANDLER ✨ ---
    balance_management_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(balance_management.start_balance_management, pattern='^admin_manage_balance$')
        ],
        states={
            balance_management.GET_USER_ID: [
                # Handler for the custom back button
                MessageHandler(filters.Regex(f'^{_("keyboards.financials.balance_management_back_button")}$'), balance_management.end_management_and_show_financial_menu),
                # Handler for the user ID
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_management.process_user_id),
            ],
            balance_management.SHOW_USER_BALANCE: [
                CallbackQueryHandler(balance_management.prompt_for_amount, pattern=r'^balance_')
            ],
            balance_management.GET_AMOUNT: [
                # This now returns to GET_USER_ID to ask for the next user
                MessageHandler(filters.TEXT & ~filters.COMMAND, balance_management.process_amount),
                 # This is a new inline button to go back from amount entry to the user menu
                CallbackQueryHandler(balance_management.show_user_balance_menu, pattern=r'^back_to_user_menu_from_amount$')
            ],
        },
        fallbacks=[
            # This handles clicks on other main menu buttons during the conversation
            MessageHandler(filters.Regex(f'^{_("keyboards.admin_main_menu.user_management")}$|^{_("keyboards.admin_main_menu.settings_and_tools")}$'), main_menu_fallback),
            # General fallbacks from auth module
            *ADMIN_CONV_FALLBACKS
        ],
    
        # Per-message basis allows for more flexible conversation flow
     
    )

        # (✨ NEW) Conversation for setting the welcome gift
    welcome_gift_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(gift.prompt_for_welcome_gift, pattern='^admin_gift_set_welcome$')],
        states={
            gift.GET_WELCOME_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift.save_welcome_gift)]
        },
        fallbacks=[CommandHandler('cancel', end_conversation_and_show_menu)],
        conversation_timeout=300,
        map_to_parent={
            ConversationHandler.END: gift.MENU
        }
    )

    # (✨ NEW) Conversation for sending the universal gift
    universal_gift_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(gift.prompt_for_universal_gift, pattern='^admin_gift_send_universal$')],
        states={
            gift.GET_UNIVERSAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift.prompt_for_gift_confirmation)],
            gift.CONFIRM_UNIVERSAL_GIFT: [MessageHandler(filters.TEXT & ~filters.COMMAND, gift.process_universal_gift)]
        },
        fallbacks=[CommandHandler('cancel', end_conversation_and_show_menu)],
        conversation_timeout=300,
        map_to_parent={
            ConversationHandler.END: gift.MENU
        }
    )

    # (✨ NEW) Main conversation handler for the gift management menu
    gift_management_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(gift.show_gift_management_menu, pattern='^admin_gift_management$')],
        states={
            gift.MENU: [
                welcome_gift_conv,
                universal_gift_conv,
                CallbackQueryHandler(show_financial_menu, pattern='^back_to_financial_settings$')
            ]
        },
        fallbacks=[CommandHandler('cancel', end_conversation_and_show_menu)],
        conversation_timeout=600,
        allow_reentry=True  # (✨ FIX) Add this line
    )

    # --- Register ALL Conversation Handlers ---
    application.add_handler(card_settings_conv)
    application.add_handler(plan_name_settings_conv)
    application.add_handler(unlimited_plans_admin.add_unlimited_plan_conv)
    application.add_handler(volumetric_plans_admin.edit_base_price_conv)
    application.add_handler(volumetric_plans_admin.add_tier_conv)
    application.add_handler(volumetric_plans_admin.edit_tier_conv)
    application.add_handler(wallet_admin.edit_amounts_conv)
    application.add_handler(balance_management_conv)
    application.add_handler(gift_management_conv)

    standalone_handlers = [
        MessageHandler(filters.Regex('^💰 تنظیمات مالی$'), show_financial_menu),
        CallbackQueryHandler(show_payment_methods_menu, pattern=r'^show_payment_methods$'),
        CallbackQueryHandler(show_plan_management_menu, pattern=r'^show_plan_management$'),
        CallbackQueryHandler(wallet_admin.show_wallet_settings_menu, pattern=r'^admin_wallet_settings$'),
        CallbackQueryHandler(show_financial_menu, pattern=r'^back_to_financial_settings$'),
        CallbackQueryHandler(back_to_main_settings_menu, pattern=r'^back_to_main_settings$'),
        CallbackQueryHandler(show_plan_management_menu, pattern=r'^back_to_plan_management$'),
        CallbackQueryHandler(unlimited_plans_admin.manage_unlimited_plans_menu, pattern=r'^admin_manage_unlimited$'),
        CallbackQueryHandler(unlimited_plans_admin.confirm_delete_plan, pattern=r'^unlimplan_delete_'),
        CallbackQueryHandler(unlimited_plans_admin.execute_delete_plan, pattern=r'^unlimplan_do_delete_'),
        CallbackQueryHandler(unlimited_plans_admin.toggle_plan_status, pattern=r'^unlimplan_toggle_'),
        CallbackQueryHandler(volumetric_plans_admin.manage_volumetric_plans_menu, pattern=r'^admin_manage_volumetric$'),
        CallbackQueryHandler(volumetric_plans_admin.confirm_delete_tier, pattern=r'^vol_delete_tier_'),
        CallbackQueryHandler(volumetric_plans_admin.execute_delete_tier, pattern=r'^vol_do_delete_tier_'),
        CallbackQueryHandler(show_coming_soon, pattern=r'^coming_soon$'),
    ]
    application.add_handlers(standalone_handlers)
    LOGGER.info("Financials settings module handlers registered successfully.")