# FILE: modules/payment/actions/wallet.py

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db_manager import load_financials, get_pending_invoice, decrease_wallet_balance
from shared.translator import _
from .approval import approve_payment # We'll need this for auto-approval

LOGGER = logging.getLogger(__name__)


async def send_wallet_charge_invoice(context: ContextTypes.DEFAULT_TYPE, user_id: int, invoice_id: int, amount: int):
    """
    Sends an invoice specifically for charging the user's wallet.
    """
    financials = await load_financials()
    if not financials.get("card_holder") or not financials.get("card_number"):
        LOGGER.error(f"Cannot send wallet charge invoice to user {user_id}: Financials not set.")
        try:
            await context.bot.send_message(chat_id=user_id, text=_("financials_payment.invoice_generation_unavailable"))
        except Exception:
            pass
        return

    invoice_text = _("financials_payment.invoice_title_wallet_charge")
    invoice_text += _("financials_payment.invoice_number", id=invoice_id)
    invoice_text += "-------------------------------------\n"
    invoice_text += _("financials_payment.invoice_price", price=f"`{amount:,.0f}`")
    invoice_text += _("financials_payment.invoice_payment_details", card_number=f"`{financials['card_number']}`", card_holder=f"`{financials['card_holder']}`")
    invoice_text += _("financials_payment.invoice_footer_prompt")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("financials_payment.button_send_receipt"), callback_data="customer_send_receipt")],
        [InlineKeyboardButton(_("financials_payment.button_back_to_menu"), callback_data="payment_back_to_menu")]
    ])
    
    try:
        await context.bot.send_message(chat_id=user_id, text=invoice_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        LOGGER.info(f"Wallet charge invoice #{invoice_id} for {amount:,} Tomans sent to user {user_id}.")
    except Exception as e:
        LOGGER.error(f"Failed to send wallet charge invoice #{invoice_id} to user {user_id}: {e}", exc_info=True)


async def pay_with_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles the user's request to pay for an invoice using their wallet balance.
    """
    query = update.callback_query
    await query.answer(_("financials_payment.processing_wallet_payment"))

    try:
        invoice_id = int(query.data.split('_')[-1])
    except (IndexError, ValueError):
        await query.edit_message_text(_("errors.internal_error"))
        return

    invoice = await get_pending_invoice(invoice_id)
    if not invoice or invoice['status'] != 'pending':
        await query.edit_message_text(_("financials_payment.invoice_already_processed_simple"))
        return

    user_id = update.effective_user.id
    price = float(invoice.get('price', 0))

    new_balance = await decrease_wallet_balance(user_id=user_id, amount=price)

    if new_balance is not None:
        # Payment successful
        await query.edit_message_text(
            _("financials_payment.wallet_payment_successful", 
              price=f"{int(price):,}", 
              new_balance=f"{int(new_balance):,}")
        )
        
        # Now, trigger the approval logic automatically.
        # We create a "mock" update object to pass to the approve_payment function.
        class MockUser:
            id = 0
            full_name = _("financials_payment.wallet_auto_payment_name")

        class MockQuery:
            data = f"approve_receipt_{invoice_id}"
            message = type('obj', (object,), {'caption' : f"Auto-approved invoice #{invoice_id}"})() # A mock message
            async def answer(self, *args, **kwargs): pass
            async def edit_message_caption(self, *args, **kwargs): pass
        
        class MockUpdate:
            effective_user = MockUser()
            callback_query = MockQuery()
            
        await approve_payment(MockUpdate(), context)

    else:
        # Payment failed (insufficient funds)
        await query.answer(_("financials_payment.wallet_payment_failed_insufficient_funds"), show_alert=True)