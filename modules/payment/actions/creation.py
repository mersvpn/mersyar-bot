# FILE: modules/payment/actions/creation.py

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db_manager import load_financials
from shared.translator import _
from shared.callback_types import SendReceipt
from shared.financial_utils import calculate_payment_details  # <--- وارد کردن موتور جدید

LOGGER = logging.getLogger(__name__)

async def send_custom_plan_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_details: dict, invoice_id: int):
    """
    Creates and sends an invoice for a new user purchasing a custom volumetric or unlimited plan.
    It now uses the central payment calculation engine to handle wallet balance.
    """
    user_id = update.effective_user.id
    volume, duration, price = plan_details.get('volume'), plan_details.get('duration'), plan_details.get('price')
    
    if not all([volume is not None, duration, price]):
        await context.bot.send_message(chat_id=user_id, text=_("financials_payment.error_processing_plan"))
        return

    financials = await load_financials()
    if not financials.get("card_holder") or not financials.get("card_number"):
        await context.bot.send_message(chat_id=user_id, text=_("financials_payment.invoice_generation_unavailable"))
        return

    # --- ✨ Modern Payment Calculation ✨ ---
    payment_info = await calculate_payment_details(user_id, price)
    payable_amount = payment_info["payable_amount"]
    paid_from_wallet = payment_info["paid_from_wallet"]
    has_sufficient_funds = payment_info["has_sufficient_funds"]
    # --- ----------------------------- ---
    
    invoice_text = _("financials_payment.invoice_title_custom_plan")
    invoice_text += _("financials_payment.invoice_number", id=invoice_id)
    invoice_text += _("financials_payment.invoice_custom_plan_volume", volume=volume)
    invoice_text += _("financials_payment.invoice_custom_plan_duration", duration=duration)
    invoice_text += "-------------------------------------\n"
    invoice_text += _("financials_payment.invoice_price", price=f"`{price:,.0f}`")
    
    # Show wallet deduction if any amount is used from it
    if paid_from_wallet > 0:
        invoice_text += _("financials_payment.invoice_wallet_deduction", amount=f"`{paid_from_wallet:,.0f}`")
    
    invoice_text += "-------------------------------------\n"
    invoice_text += _("financials_payment.invoice_payable_amount", amount=f"`{payable_amount:,.0f}`")
    
    if payable_amount > 0:
        invoice_text += _("financials_payment.invoice_payment_details", card_number=f"`{financials['card_number']}`", card_holder=f"`{financials['card_holder']}`")
        invoice_text += _("financials_payment.invoice_footer_prompt")
    
    # --- Modernized Keyboard Logic ---
    keyboard_rows = []
    
    # If the entire amount can be paid from the wallet, show only the wallet payment button
    if has_sufficient_funds:
        wallet_button_text = _("financials_payment.button_pay_with_wallet_full", price=f"{int(price):,}")
        keyboard_rows.append([
            InlineKeyboardButton(wallet_button_text, callback_data=f"wallet_pay_{invoice_id}")
        ])
    # If there's an amount to pay, show the 'Send Receipt' button
    elif payable_amount > 0:
        send_receipt_callback = SendReceipt(invoice_id=invoice_id).to_string()
        keyboard_rows.append(
            [InlineKeyboardButton(_("financials_payment.button_send_receipt"), callback_data=send_receipt_callback)]
        )

    keyboard_rows.append([InlineKeyboardButton(_("financials_payment.button_back_to_menu"), callback_data="payment_back_to_menu")])
    keyboard = InlineKeyboardMarkup(keyboard_rows)
    
    try:
        await context.bot.send_message(chat_id=user_id, text=invoice_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        LOGGER.info(f"Custom plan invoice #{invoice_id} sent to user {user_id}. Payable: {payable_amount}, From Wallet: {paid_from_wallet}")
    except Exception as e:
        LOGGER.error(f"Failed to send custom plan invoice #{invoice_id} to user {user_id}: {e}", exc_info=True)
        try:
            await context.bot.send_message(chat_id=user_id, text=_("financials_payment.error_sending_invoice"))
        except Exception:
            pass