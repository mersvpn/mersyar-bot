# FILE: financials/handler.py (نسخه نهایی با هر دو پنل مدیریت پلن)

import logging
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

# --- Local Imports ---
from .actions.settings import (
    card_settings_conv,
    plan_name_settings_conv,
    show_financial_menu,
    show_payment_methods_menu,
    show_plan_management_menu
)
from .actions.payment import (
    payment_request_conv,
    handle_payment_back_button,
    approve_payment,
    reject_payment,
    confirm_manual_payment
)
# --- MODIFIED: Import both new admin panel modules ---
from .actions import unlimited_plans_admin, volumetric_plans_admin
from shared.callbacks import show_coming_soon

# --- SETUP ---
LOGGER = logging.getLogger(__name__)

# ===== REGISTRATION =====
def register(application: Application):
    """Registers all handlers for the financials module."""
    LOGGER.info("Registering financials module handlers...")
    
    # =============================================================================
    #  1. ثبت مکالمات و هندلرهای ادمین (گروه 0)
    # =============================================================================

    # --- Main Menus ---
    application.add_handler(MessageHandler(filters.Regex('^💰 تنظیمات مالی$'), show_financial_menu), group=0)
    application.add_handler(MessageHandler(filters.Regex('^💳 تنظیمات پرداخت$'), show_payment_methods_menu), group=0)
    application.add_handler(MessageHandler(filters.Regex('^📊 مدیریت پلن‌های فروش$'), show_plan_management_menu), group=0)

    # --- "Back" Buttons ---
    application.add_handler(CallbackQueryHandler(show_financial_menu, pattern=r'^back_to_financial_settings$'), group=0)
    application.add_handler(CallbackQueryHandler(show_payment_methods_menu, pattern=r'^back_to_payment_methods$'), group=0)
    application.add_handler(CallbackQueryHandler(show_plan_management_menu, pattern=r'^back_to_plan_management$'), group=0)

    # --- Conversations ---
    application.add_handler(card_settings_conv, group=0)
    application.add_handler(payment_request_conv, group=0)
    application.add_handler(plan_name_settings_conv, group=0)
    application.add_handler(unlimited_plans_admin.add_unlimited_plan_conv, group=0)
    # --- NEW: Register conversations for volumetric plan management ---
    application.add_handler(volumetric_plans_admin.edit_base_price_conv, group=0)
    application.add_handler(volumetric_plans_admin.add_tier_conv, group=0)
    application.add_handler(volumetric_plans_admin.edit_tier_conv, group=0)


    # --- Unlimited Plan Management Handlers ---
    application.add_handler(CallbackQueryHandler(unlimited_plans_admin.manage_unlimited_plans_menu, pattern=r'^admin_manage_unlimited$'), group=0)
    application.add_handler(CallbackQueryHandler(unlimited_plans_admin.confirm_delete_plan, pattern=r'^unlimplan_delete_'), group=0)
    application.add_handler(CallbackQueryHandler(unlimited_plans_admin.execute_delete_plan, pattern=r'^unlimplan_do_delete_'), group=0)
    application.add_handler(CallbackQueryHandler(unlimited_plans_admin.toggle_plan_status, pattern=r'^unlimplan_toggle_'), group=0)
    
    # --- NEW: Handlers for Volumetric Plan Management ---
    application.add_handler(CallbackQueryHandler(volumetric_plans_admin.manage_volumetric_plans_menu, pattern=r'^admin_manage_volumetric$'), group=0)
    application.add_handler(CallbackQueryHandler(volumetric_plans_admin.confirm_delete_tier, pattern=r'^vol_delete_tier_'), group=0)
    application.add_handler(CallbackQueryHandler(volumetric_plans_admin.execute_delete_tier, pattern=r'^vol_do_delete_tier_'), group=0)


    # --- Receipt Approval/Rejection Handlers ---
    application.add_handler(CallbackQueryHandler(approve_payment, pattern=r'^approve_receipt_'), group=0)
    application.add_handler(CallbackQueryHandler(confirm_manual_payment, pattern=r'^confirm_manual_receipt_'), group=0)
    application.add_handler(CallbackQueryHandler(reject_payment, pattern=r'^reject_receipt_'), group=0)

    # --- Placeholder Handler ---
    application.add_handler(CallbackQueryHandler(show_coming_soon, pattern=r'^coming_soon$'), group=0)
    
    LOGGER.debug("Admin handlers for financials module registered.")

    # =============================================================================
    #  2. ثبت هندلرهای مشتری (گروه 1)
    # =============================================================================
    application.add_handler(CallbackQueryHandler(handle_payment_back_button, pattern=r'^payment_back_to_menu$'), group=1)
    
    LOGGER.info("Financials module handlers registered successfully.")

    