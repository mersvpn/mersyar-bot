# --- START OF FILE modules/payment/actions/manual.py ---
import logging
from decimal import Decimal
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler,
    CommandHandler, filters, CallbackQueryHandler
)
from telegram.constants import ParseMode

from database.crud import financial_setting as crud_financial
from database.crud import user_note as crud_user_note
from database.crud import pending_invoice as crud_invoice
from database.crud import user as crud_user
from shared.keyboards import get_admin_main_menu_keyboard
from modules.general.actions import start as back_to_main_menu_action
from config import config
from shared.translator import _
from shared.callback_types import StartManualInvoice, SendReceipt

GET_MANUAL_PRICE = 0
LOGGER = logging.getLogger(__name__)

async def start_manual_invoice_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not update.effective_user or update.effective_user.id not in config.AUTHORIZED_USER_IDS:
        if query: await query.answer(_("financials_payment.access_denied"), show_alert=True)
        return ConversationHandler.END

    await query.answer()
    
    callback_obj = StartManualInvoice.from_string(query.data)
    if not callback_obj:
        LOGGER.error(f"Invalid callback data for payment request: {query.data}")
        await query.edit_message_text(_("financials_payment.invalid_callback_data"))
        return ConversationHandler.END
    
    marzban_username = callback_obj.username
    customer_id = callback_obj.customer_id

    if customer_id == 0:
        user_db_info = await crud_user.get_user_by_marzban_username(marzban_username)
        if user_db_info and user_db_info.user_id:
            customer_id = user_db_info.user_id
        else:
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

# --- START OF REVISED FUNCTION ---
async def process_manual_price_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
        
    financials = await crud_financial.load_financial_settings()
    if not financials or not financials.card_holder or not financials.card_number:
        await update.message.reply_text(_("financials_payment.error_financials_not_set"), parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    # Step 1: Update the user_note with the new price.
    await crud_user_note.create_or_update_user_note(
        marzban_username=marzban_username,
        price=price_int
    )

    # Step 2: Read the note (which now includes the price) to get all details.
    user_note = await crud_user_note.get_user_note(marzban_username)
    if not user_note:
        LOGGER.error(f"Failed to read user_note for {marzban_username} immediately after saving.")
        await update.message.reply_text(_("errors.internal_error"))
        return ConversationHandler.END

    duration = user_note.subscription_duration or 0
    volume = user_note.subscription_data_limit_gb or 0

    # Step 3: Create plan_details with a consistent, simple invoice type.
    plan_details = {
        'invoice_type': 'MANUAL_INVOICE', # Use a single type for all manual invoices
        'username': marzban_username,
        'duration': duration,
        'volume': volume,
        'price': price_int
    }

    invoice = await crud_invoice.create_pending_invoice({
        'user_id': customer_id,
        'plan_details': plan_details,
        'price': price_int,
        'from_wallet_amount': 0
    })

    if not invoice:
        await update.message.reply_text(_("financials_payment.error_creating_invoice_db"))
        return ConversationHandler.END

    invoice_id = invoice.invoice_id
    LOGGER.info(f"Admin created manual invoice #{invoice_id} for user '{marzban_username}'.")

    try:
        payment_message = _("financials_payment.invoice_title_subscription")
        payment_message += _("financials_payment.invoice_number", id=invoice_id)
        payment_message += _("financials_payment.invoice_service", username=f"`{marzban_username}`")
        payment_message += _("financials_payment.invoice_price", price=f"`{price_int:,}`")
        payment_message += _("financials_payment.invoice_payment_details", card_number=f"`{financials.card_number}`", card_holder=f"`{financials.card_holder}`")
        payment_message += _("financials_payment.invoice_footer_prompt")
        
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
# --- END OF REVISED FUNCTION ---

async def cancel_manual_invoice_conv(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(_("financials_payment.manual_invoice_cancelled"), reply_markup=get_admin_main_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

manual_invoice_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_manual_invoice_conv, pattern=f"^{StartManualInvoice.PREFIX}:")],
    states={GET_MANUAL_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_manual_price_and_send)]},
    fallbacks=[CommandHandler('cancel', cancel_manual_invoice_conv), CommandHandler('start', back_to_main_menu_action)],
    conversation_timeout=300, per_user=True, per_chat=True
)

# --- END OF FILE modules/payment/actions/manual.py ---```