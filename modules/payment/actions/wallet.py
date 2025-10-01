# FILE: modules/payment/actions/wallet.py

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from shared.callback_types import SendReceipt 
from database.db_manager import load_financials, get_pending_invoice, decrease_wallet_balance, get_user_by_id
from shared.translator import _
from .approval import approve_payment
from shared.log_channel import send_log

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
    
    send_receipt_callback = SendReceipt(invoice_id=invoice_id).to_string()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(_("financials_payment.button_send_receipt"), callback_data=send_receipt_callback)],
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

    LOGGER.info(f"Start pay_with_wallet called: user_id={user_id}, invoice_id={invoice_id}, amount={price}")

    new_balance = await decrease_wallet_balance(user_id=user_id, amount=price)

    if new_balance is not None:
        LOGGER.info(f"Wallet balance decreased successfully for user_id={user_id}, amount={price}")

        await query.edit_message_text(
            _("financials_payment.wallet_payment_successful",
              price=f"{int(price):,}",
              new_balance=f"{int(new_balance):,}")
        )

        # --- START: INTELLIGENT LOGGING TO CHANNEL ---
        db_user = await get_user_by_id(user_id)
        customer_name = db_user.get('username', f"ID: {user_id}") if db_user else f"ID: {user_id}"
        plan_details = invoice.get('plan_details', {})
        invoice_type = plan_details.get("invoice_type")
        log_message = ""

        if invoice_type == "RENEWAL":
            username = plan_details.get('username', 'N/A')
            duration = plan_details.get('duration', 0)
            volume = plan_details.get('volume', 0)
            volume_text = _("marzban_display.unlimited") if volume == 0 else f"{volume} گیگابایت"
            log_message = _("log.wallet_renewal_success",
                            invoice_id=invoice_id,
                            username=f"`{username}`",
                            volume=volume_text,
                            duration=duration,
                            price=f"{int(price):,}",
                            customer_name=customer_name,
                            customer_id=user_id,
                            new_balance=f"{int(new_balance):,}")
        elif invoice_type in ["NEW_USER_CUSTOM", "NEW_USER_UNLIMITED"]:
            username = plan_details.get('username', 'N/A')
            duration = plan_details.get('duration', 0)
            volume = plan_details.get('volume', 0)
            volume_text = _("marzban_display.unlimited") if volume == 0 else f"{volume} گیگابایت"
            log_message = _("log.wallet_new_user_success",
                            invoice_id=invoice_id,
                            username=f"`{username}`",
                            volume=volume_text,
                            duration=duration,
                            price=f"{int(price):,}",
                            customer_name=customer_name,
                            customer_id=user_id,
                            new_balance=f"{int(new_balance):,}")
        elif invoice_type == "DATA_TOP_UP":
            username = plan_details.get('username', 'N/A')
            volume = plan_details.get('volume', 0)
            log_message = _("log.wallet_data_topup_success",
                            invoice_id=invoice_id,
                            username=f"`{username}`",
                            volume=volume,
                            price=f"{int(price):,}",
                            customer_name=customer_name,
                            customer_id=user_id,
                            new_balance=f"{int(new_balance):,}")
        else:
            # Fallback for manual invoices or other types
            log_message = _("log.wallet_generic_payment_success",
                            invoice_id=invoice_id,
                            price=f"{int(price):,}",
                            customer_name=customer_name,
                            customer_id=user_id,
                            new_balance=f"{int(new_balance):,}")

        await send_log(context.bot, log_message, parse_mode=ParseMode.MARKDOWN)
        # --- END: INTELLIGENT LOGGING ---

        # Trigger the approval logic automatically.
        class MockUser:
            id = 0
            full_name = _("financials_payment.wallet_auto_payment_name_system")

        class MockQuery:
            data = f"approve_receipt_{invoice_id}"
            message = type('obj', (object,), {'caption': f"Auto-approved invoice #{invoice_id} via wallet"})()

            async def answer(self, *args, **kwargs): pass
            async def edit_message_caption(self, *args, **kwargs): pass

        class MockUpdate:
            effective_user = MockUser()
            callback_query = MockQuery()

        await approve_payment(MockUpdate(), context)

    else:
        await query.answer(_("financials_payment.wallet_payment_failed_insufficient_funds"), show_alert=True)
        LOGGER.warning(f"Failed to decrease wallet balance for user_id={user_id}, amount={price}")
