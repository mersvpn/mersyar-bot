# FILE: modules/payment/actions/renewal.py

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError

from database.db_manager import (
    load_financials, get_user_note, get_telegram_id_from_marzban_username,
    create_pending_invoice, get_user_wallet_balance
)
from shared.translator import _
from shared.callback_types import SendReceipt, StartManualInvoice 

LOGGER = logging.getLogger(__name__)


async def send_renewal_invoice_to_user(context: ContextTypes.DEFAULT_TYPE, user_telegram_id: int, username: str, renewal_days: int, price: int, data_limit_gb: int):
    """
    Creates and sends a standardized renewal invoice to a user.
    """
    try:
        financials = await load_financials()
        if not financials.get("card_holder") or not financials.get("card_number"):
            LOGGER.error(f"Cannot send renewal invoice to {username}: Financial settings not configured.")
            return

        plan_details = {
    'username': username, 
    'volume': data_limit_gb, 
    'duration': renewal_days,
    'invoice_type': 'RENEWAL'  # <-- ADD THIS LINE
}
        invoice_id = await create_pending_invoice(user_telegram_id, plan_details, price)
        if not invoice_id:
            LOGGER.error(f"Failed to create renewal invoice for {username}.")
            return

        invoice_text = _("financials_payment.invoice_title_renewal")
        invoice_text += _("financials_payment.invoice_number", id=invoice_id)
        invoice_text += _("financials_payment.invoice_service", username=f"`{username}`")
        invoice_text += _("financials_payment.invoice_renewal_period", days=renewal_days)
        invoice_text += _("financials_payment.invoice_price", price=f"`{price:,}`")
        invoice_text += _("financials_payment.invoice_payment_details", card_number=f"`{financials['card_number']}`", card_holder=f"`{financials['card_holder']}`")
        invoice_text += _("financials_payment.invoice_footer_prompt")
        
        # --- Wallet Payment Button Logic ---
        send_receipt_callback = SendReceipt(invoice_id=invoice_id).to_string()
        keyboard_rows = [
            [InlineKeyboardButton(_("financials_payment.button_send_receipt"), callback_data=send_receipt_callback)]
        ]
        user_balance = await get_user_wallet_balance(user_telegram_id)
        if user_balance is not None and user_balance >= price:
            wallet_button_text = _("financials_payment.button_pay_with_wallet", balance=f"{int(user_balance):,}")
            keyboard_rows.insert(0, [
                InlineKeyboardButton(wallet_button_text, callback_data=f"wallet_pay_{invoice_id}")
            ])

        keyboard_rows.append([InlineKeyboardButton(_("financials_payment.button_back_to_menu"), callback_data="payment_back_to_menu")])
        keyboard = InlineKeyboardMarkup(keyboard_rows)

        await context.bot.send_message(chat_id=user_telegram_id, text=invoice_text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        LOGGER.info(f"Renewal invoice #{invoice_id} sent to user {username} ({user_telegram_id}).")
    except TelegramError as e:
        if "bot was blocked" in str(e).lower():
            LOGGER.warning(f"Could not send renewal invoice to {user_telegram_id}: User blocked the bot.")
        else:
            LOGGER.error(f"Telegram error sending renewal invoice to {user_telegram_id}: {e}", exc_info=True)
    except Exception as e:
        LOGGER.error(f"Unexpected error in send_renewal_invoice_to_user for {username}: {e}", exc_info=True)


async def send_manual_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for the admin button to send a renewal invoice based on saved user notes.
    """
    query = update.callback_query
    await query.answer()
    username = query.data.split('_', 2)[-1]
    admin_chat_id = update.effective_chat.id

    try:
        customer_id = await get_telegram_id_from_marzban_username(username)
        if not customer_id:
            await context.bot.send_message(admin_chat_id, _("financials_payment.error_customer_telegram_not_found", username=f"`{username}`"), parse_mode=ParseMode.MARKDOWN)
            return
            
        note_data = await get_user_note(username)
        price = note_data.get('subscription_price')
        duration = note_data.get('subscription_duration')
        
        # Correctly check for None instead of just Falsy values (like 0)
        if price is None or duration is None:
            # If no subscription info, redirect admin to the manual invoice creation conversation
            callback_obj = StartManualInvoice(customer_id=customer_id, username=username)
            admin_keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(
                _("financials_payment.button_create_send_invoice"), 
                callback_data=callback_obj.to_string()
            )]])
            await context.bot.send_message(
                admin_chat_id, 
                _("financials_payment.note_not_set_prompt_manual_invoice", username=f"`{username}`"), 
                reply_markup=admin_keyboard, 
                parse_mode=ParseMode.MARKDOWN
            )
            return

        # Use the central function to send the invoice
        await send_renewal_invoice_to_user(
            context,
            user_telegram_id=customer_id,
            username=username,
            renewal_days=duration,
            price=price,
            data_limit_gb=note_data.get('subscription_data_limit_gb', 0)
        )
        await context.bot.send_message(admin_chat_id, _("financials_payment.invoice_sent_to_user_success_no_id"))

    except Exception as e:
        LOGGER.error(f"Failed to send manual invoice for user {username}: {e}", exc_info=True)
        await context.bot.send_message(admin_chat_id, _("financials_payment.unknown_error"), parse_mode=ParseMode.MARKDOWN)