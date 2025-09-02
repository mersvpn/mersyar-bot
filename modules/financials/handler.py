# FILE: financials/handler.py (نسخه نهایی با لاگ برای دیباگ)

import logging
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

# --- Local Imports ---
from .actions.settings import (
    card_settings_conv,
    pricing_conv,
    show_financial_menu,
    show_payment_methods_menu
)
from .actions.payment import (
    payment_request_conv, 
    handle_copy_button, 
    handle_payment_back_button,
    approve_payment, 
    reject_payment,
    confirm_manual_payment  # <-- ویرگول در انتهای خط قبلی اضافه شد
)
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

    # --- منوهای جدید ---
    application.add_handler(MessageHandler(filters.Regex('^💰 تنظیمات مالی$'), show_financial_menu), group=0)
    application.add_handler(MessageHandler(filters.Regex('^💳 تنظیمات پرداخت$'), show_payment_methods_menu), group=0)
    application.add_handler(CallbackQueryHandler(show_financial_menu, pattern=r'^back_to_financial_settings$'), group=0)

    # --- مکالمات (Conversations) ---
    application.add_handler(card_settings_conv, group=0)
    application.add_handler(pricing_conv, group=0) # این مکالمه نقطه ورود خودش را دارد
    application.add_handler(payment_request_conv, group=0)

    # --- هندلرهای تایید/رد رسید ---
    application.add_handler(CallbackQueryHandler(approve_payment, pattern=r'^approve_receipt_'), group=0)
    application.add_handler(CallbackQueryHandler(confirm_manual_payment, pattern=r'^confirm_manual_receipt_'), group=0) # <-- این خط اضافه شد
    application.add_handler(CallbackQueryHandler(reject_payment, pattern=r'^reject_receipt_'), group=0)

    # --- هندلر برای دکمه‌های غیرفعال ---
    application.add_handler(CallbackQueryHandler(show_coming_soon, pattern=r'^coming_soon$'), group=0)
    
    LOGGER.debug("Admin handlers for financials module registered.")

    # =============================================================================
    #  2. ثبت هندلرهای مشتری (گروه 1)
    # =============================================================================
    application.add_handler(CallbackQueryHandler(handle_copy_button, pattern=r'^copy_text:'), group=1)
    application.add_handler(CallbackQueryHandler(handle_payment_back_button, pattern=r'^payment_back_to_menu$'), group=1)
    
    LOGGER.info("Financials module handlers registered successfully.")