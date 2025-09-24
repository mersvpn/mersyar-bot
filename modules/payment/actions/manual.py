# FILE: modules/payment/actions/manual.py (MODIFIED FOR CALLBACK_TYPES)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CommandHandler, filters
)
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler

# --- MODIFIED: Added get_user_by_marzban_username ---
from database.db_manager import load_financials, get_user_note, create_pending_invoice, get_user_by_marzban_username
from shared.keyboards import get_admin_main_menu_keyboard
from modules.general.actions import start as back_to_main_menu_action
from config import config
from shared.translator import _
# --- MODIFIED: Import new callback types ---
from shared.callback_types import StartManualInvoice, SendReceipt

# Using a more specific name for the state
GET_MANUAL_PRICE = 0

LOGGER = logging.getLogger(__name__)


async def start_manual_invoice_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation for an admin to create a manual invoice."""
    query = update.callback_query
    if not update.effective_user or update.effective_user.id not in config.AUTHORIZED_USER_IDS:
        if query: await query.answer(_("financials_payment.access_denied"), show_alert=True)
        return ConversationHandler.END

    await query.answer()
    
    # --- MODIFIED: Use the new callback class to parse data ---
    callback_obj = StartManualInvoice.from_string(query.data)
    if not callback_obj:
        LOGGER.error(f"Invalid callback data for payment request: {query.data}")
        await query.edit_message_text(_("financials_payment.invalid_callback_data"))
        return ConversationHandler.END
    
    marzban_username = callback_obj.username
    customer_id = callback_obj.customer_id

    # If customer_id was a placeholder (0), try to find the real one from the database
    if customer_id == 0:
        user_db_info = await get_user_by_marzban_username(marzban_username)
        if user_db_info and user_db_info.get('telegram_id'):
            customer_id = user_db_info['telegram_id']
        else:
            # If still not found, inform the admin and end the conversation
            await query.edit_message_text(
                _("financials_payment.error_customer_id_not_found", username=f"`{marzban_username}`"),
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END
            
    context.user_data['payment_info'] = {'customer_id': customer_id, 'marzban_username': marzban_username}
    
    await query.edit_message_text(
        text=_("financials_payment.manual_invoice_prompt", username=f"`{marzban_username}`"),
        parse_mode=ParseMode.MARKDOWN
    )
    return GET_MANUAL_PRICE


async def process_manual_price_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the price entered by the admin and sends the manual invoice."""
    payment_info = context.user_data.get('payment_info')
    if not payment_info:
        await update.message.reply_text(_("financials_payment.error_user_info_lost"))
        return ConversationHandler.END
        
    customer_id, marzban_username = payment_info['customer_id'], payment_info['marzban_username']
    
    try:
        price_int = int(update.message.text.strip())
        if price_int <= 0: raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(_("financials_payment.invalid_price_input"))
        return GET_MANUAL_PRICE
        
    financials = await load_financials()
    if not financials.get("card_holder") or not financials.get("card_number"):
        await update.message.reply_text(_("financials_payment.error_financials_not_set"), parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    user_note = await get_user_note(marzban_username)
    if not user_note:
        LOGGER.warning(f"No subscription note found for {marzban_username} while creating manual invoice.")

    # Get current duration and volume, but overwrite price with the admin's input
    duration = user_note.get('subscription_duration', 0) if user_note else 0
    volume = user_note.get('subscription_data_limit_gb', 0) if user_note else 0
    
    plan_details = {
        'username': marzban_username,
        'volume': volume,
        'duration': duration,
        'price': price_int,  # <-- IMPORTANT: Save the manually entered price
        'invoice_type': 'MANUAL_INVOICE' # <-- IMPORTANT: Mark this invoice type
    }

    # Pass price_int to create_pending_invoice as it's the final price
    invoice_id = await create_pending_invoice(customer_id, plan_details, price_int)
    if not invoice_id:
        await update.message.reply_text(_("financials_payment.error_creating_invoice_db"))
        return ConversationHandler.END

    LOGGER.info(f"Admin created manual invoice #{invoice_id} for user '{marzban_username}'.")

    try:
        payment_message = _("financials_payment.invoice_title_subscription")
        payment_message += _("financials_payment.invoice_number", id=invoice_id)
        payment_message += _("financials_payment.invoice_service", username=f"`{marzban_username}`")
        payment_message += _("financials_payment.invoice_price", price=f"`{price_int:,}`")
        payment_message += _("financials_payment.invoice_payment_details", card_number=financials['card_number'], card_holder=financials['card_holder'])
        payment_message += _("financials_payment.invoice_footer_prompt")
        
        # --- MODIFIED: Use the new callback class to build the button data ---
        send_receipt_callback = SendReceipt(invoice_id=invoice_id).to_string()
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("financials_payment.button_send_receipt"), callback_data=send_receipt_callback)],
            [InlineKeyboardButton(_("financials_payment.button_back_to_menu"), callback_data="payment_back_to_menu")]
        ])
        
        await context.bot.send_message(chat_id=customer_id, text=payment_message, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
        await update.message.reply_text(_("financials_payment.invoice_sent_to_user_success", id=invoice_id, customer_id=customer_id))
    except Exception as e:
        LOGGER.error(f"Failed to send manual invoice details to customer {customer_id}: {e}", exc_info=True)
        await update.message.reply_text(_("financials_payment.error_sending_message_to_customer"))
    
    context.user_data.clear()
    await update.message.reply_text(_("financials_payment.back_to_main_menu"), reply_markup=get_admin_main_menu_keyboard())
    return ConversationHandler.END


async def cancel_manual_invoice_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels the manual invoice creation conversation."""
    await update.message.reply_text(_("financials_payment.manual_invoice_cancelled"), reply_markup=get_admin_main_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


manual_invoice_conv = ConversationHandler(
    # --- MODIFIED: Use the PREFIX from the new callback class for the pattern ---
    entry_points=[CallbackQueryHandler(start_manual_invoice_conv, pattern=f"^{StartManualInvoice.PREFIX}:")],
    states={GET_MANUAL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_manual_price_and_send)]},
    fallbacks=[CommandHandler('cancel', cancel_manual_invoice_conv), CommandHandler('start', back_to_main_menu_action)],
    conversation_timeout=300, per_user=True, per_chat=True
)