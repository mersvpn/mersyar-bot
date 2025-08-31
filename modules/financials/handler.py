# FILE: financials/handler.py
# (نسخه نهایی با هندلرهای تایید و رد رسید)

# ===== IMPORTS & DEPENDENCIES =====
from telegram.ext import Application, CallbackQueryHandler

from .actions.settings import financial_conv
# --- START: FIX - Import new handlers ---
from .actions.payment import (
    payment_request_conv, handle_copy_button, handle_payment_back_button,
    approve_payment, reject_payment
)
# --- END: FIX ---

# ===== REGISTRATION =====
def register(application: Application):
    """Registers all handlers for the financials module."""
    # Register admin-facing conversations and handlers (group 0)
    application.add_handler(financial_conv, group=0)
    application.add_handler(payment_request_conv, group=0)

    # ======================== START: NEW ADMIN HANDLERS ========================
    # These handlers are for admins to approve/reject receipts.
    application.add_handler(CallbackQueryHandler(approve_payment, pattern=r'^approve_receipt_'), group=0)
    application.add_handler(CallbackQueryHandler(reject_payment, pattern=r'^reject_receipt_'), group=0)
    # ========================= END: NEW ADMIN HANDLERS =========================

    # --- Register customer-facing callback handlers ---
    # These are public, so they are in group 1.
    application.add_handler(CallbackQueryHandler(handle_copy_button, pattern=r'^copy_text:'), group=1)
    application.add_handler(CallbackQueryHandler(handle_payment_back_button, pattern=r'^payment_back_to_menu$'), group=1)