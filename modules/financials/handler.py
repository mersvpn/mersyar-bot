# ===== IMPORTS & DEPENDENCIES =====
from telegram.ext import Application, CallbackQueryHandler
from .actions.settings import financial_conv
from .actions.payment import payment_request_conv, handle_copy_button, handle_payment_back_button

# ===== REGISTRATION =====
def register(application: Application):
    """Registers all handlers for the financials module."""
    # Register admin-facing conversations
    application.add_handler(financial_conv, group=0)
    application.add_handler(payment_request_conv, group=0)

    # --- NEW: Register customer-facing callback handlers ---
    # These are public, so they are in group 1.
    application.add_handler(CallbackQueryHandler(handle_copy_button, pattern=r'^copy_text:'), group=1)
    application.add_handler(CallbackQueryHandler(handle_payment_back_button, pattern=r'^payment_back_to_menu$'), group=1)