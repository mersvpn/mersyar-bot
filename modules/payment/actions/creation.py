# FILE: modules/payment/actions/creation.py

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.db_manager import load_financials, get_user_wallet_balance
from shared.translator import _

LOGGER = logging.getLogger(__name__)

async def send_custom_plan_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, plan_details: dict, invoice_id: int):
    """
    Creates and sends an invoice for a new user purchasing a custom volumetric or unlimited plan.
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

    invoice_text = _("financials_payment.invoice_title_custom_plan")
    invoice_text += _("financials_payment.invoice_number", id=invoice_id)
    invoice_text += _("financials_payment.invoice_custom_plan_volume", volume=volume)
    invoice_text += _("financials_payment.invoice_custom_plan_duration", duration=duration)
    invoice_text += "-------------------------------------\n"
    invoice_text += _("financials_payment.invoice_price", price=f"`{price:,.0f}`")
    invoice_text += _("financials_payment.invoice_payment_details", card_number=f"`{financials['card_number']}`", card_holder=f"`{financials['card_holder']}`")
    invoice_text += _("financials_payment.invoice_footer_prompt")
    
    # --- Wallet Payment Button Logic ---
    keyboard_rows = [
        [InlineKeyboardButton(_("financials_payment.button_send_receipt"), callback_data="customer_send_receipt")]
    ]
    
    user_balance = await get_user_wallet_balance(user_id)
    if user_balance is not None and user_balance >= price:
        wallet_button_text = _("financials_payment.button_pay_with_wallet", balance=f"{int(user_balance):,}")
        keyboard_rows.insert(0, [
            InlineKeyboardButton(wallet_button_text, callback_data=f"wallet_pay_{invoice_id}")
        ])

    keyboard_rows.append([InlineKeyboardButton(_("financials_payment.button_back_to_menu"), callback_data="payment_back_to_menu")])
    keyboard = InlineKeyboardMarkup(keyboard_rows)
    
    try:
        await context.bot.send_message(chat_id=user_id, text=invoice_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        LOGGER.info(f"Custom plan invoice #{invoice_id} sent to user {user_id}.")
    except Exception as e:
        LOGGER.error(f"Failed to send custom plan invoice #{invoice_id} to user {user_id}: {e}", exc_info=True)
        try:
            await context.bot.send_message(chat_id=user_id, text=_("financials_payment.error_sending_invoice"))
        except Exception:
            pass