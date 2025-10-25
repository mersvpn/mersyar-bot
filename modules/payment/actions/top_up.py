# FILE: modules/payment/actions/top_up.py

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from database.crud import load_financials, get_user_wallet_balance, create_pending_invoice
from shared.translator import _

LOGGER = logging.getLogger(__name__)


async def send_data_top_up_invoice(context: ContextTypes.DEFAULT_TYPE, user_id: int, username: str, data_gb: int, price: int):
    """
    Creates and sends an invoice for a data top-up request.
    """
    try:
        financials = await crud_financial.get_financial_settings()
        if not financials.get("card_holder") or not financials.get("card_number"):
            LOGGER.error(f"Cannot send data top-up invoice to {username}: Financial settings not configured.")
            # Optionally, notify the user
            try:
                await context.bot.send_message(chat_id=user_id, text=_("financials_payment.invoice_generation_unavailable"))
            except Exception:
                pass
            return

        # Crucially, we set the 'invoice_type' to DATA_TOP_UP so the approval function knows what to do.
        plan_details = {
            'username': username, 
            'volume': data_gb,
            'invoice_type': 'DATA_TOP_UP'
        }
        invoice_id = await create_pending_invoice(user_id, plan_details, price)
        if not invoice_id:
            LOGGER.error(f"Failed to create data top-up invoice for {username}.")
            return

        invoice_text = _("financials_payment.invoice_title_top_up")
        invoice_text += _("financials_payment.invoice_number", id=invoice_id)
        invoice_text += _("financials_payment.invoice_service", username=f"`{username}`")
        invoice_text += _("financials_payment.invoice_top_up_volume", volume=data_gb)
        invoice_text += "-------------------------------------\n"
        invoice_text += _("financials_payment.invoice_price", price=f"`{price:,}`")
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

        await context.bot.send_message(chat_id=user_id, text=invoice_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        LOGGER.info(f"Data top-up invoice #{invoice_id} ({data_gb}GB for {price} Tomans) sent to user {username} ({user_id}).")

    except Exception as e:
        LOGGER.error(f"Unexpected error in send_data_top_up_invoice for {username}: {e}", exc_info=True)