# FILE: modules/customer/actions/charge.py

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from database import db_manager
from shared.translator import _
from .wallet import DISPLAY_PANEL

LOGGER = logging.getLogger(__name__)

CHOOSE_AMOUNT, GET_CUSTOM_AMOUNT, CONFIRM_CHARGE = range(1, 4)

CALLBACK_PREFIX_AMOUNT = "wallet_charge_amount_"
CALLBACK_CUSTOM_AMOUNT = "wallet_charge_custom"
CALLBACK_CONFIRM_FINAL = "wallet_charge_confirm_final"
CALLBACK_CANCEL_CHARGE = "wallet_charge_cancel"

async def start_charge_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    predefined_amounts = [50000, 100000, 250000, 500000]

    keyboard = []
    for i in range(0, len(predefined_amounts), 2):
        row = []
        amount1 = predefined_amounts[i]
        row.append(InlineKeyboardButton(
            f"💳 {amount1:,} تومان", callback_data=f"{CALLBACK_PREFIX_AMOUNT}{amount1}"
        ))
        if i + 1 < len(predefined_amounts):
            amount2 = predefined_amounts[i+1]
            row.append(InlineKeyboardButton(
                f"💳 {amount2:,} تومان", callback_data=f"{CALLBACK_PREFIX_AMOUNT}{amount2}"
            ))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(_("wallet.charge.button_custom_amount"), callback_data=CALLBACK_CUSTOM_AMOUNT)])
    keyboard.append([InlineKeyboardButton(_("wallet.charge.button_cancel"), callback_data=CALLBACK_CANCEL_CHARGE)])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = _("wallet.charge.prompt_for_amount")

    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    
    return CHOOSE_AMOUNT

async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int) -> int:
    query = update.callback_query
    if query:
        await query.answer()
        target_message = query.message
    else:
        target_message = context.user_data.get('wallet_panel_message')
        
    context.user_data['charge_amount'] = amount
    
    text = _("wallet.charge.confirm_preview", amount=f"{amount:,}")
    
    keyboard = [
        [InlineKeyboardButton(_("wallet.charge.button_confirm_final"), callback_data=CALLBACK_CONFIRM_FINAL)],
        [InlineKeyboardButton(_("wallet.charge.button_cancel"), callback_data=CALLBACK_CANCEL_CHARGE)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await target_message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    return CONFIRM_CHARGE

async def handle_predefined_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    amount_str = query.data.replace(CALLBACK_PREFIX_AMOUNT, "")
    amount = int(amount_str)
    return await show_confirmation(update, context, amount)

async def prompt_for_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    text = _("wallet.charge.prompt_for_custom_amount")
    
    keyboard = [[InlineKeyboardButton(_("wallet.charge.button_cancel"), callback_data=CALLBACK_CANCEL_CHARGE)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    return GET_CUSTOM_AMOUNT

async def handle_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    amount_text = update.message.text
    try:
        amount = int(amount_text)
        if amount < 10000:
            await update.message.reply_text(_("wallet.charge.amount_too_low", min_amount="10,000"))
            return GET_CUSTOM_AMOUNT
        
        await update.message.delete()
        
        class MockQuery:
            message = context.user_data.get('wallet_panel_message')
            async def answer(self): pass
        
        mock_update = Update(update.update_id, callback_query=MockQuery())
        return await show_confirmation(mock_update, context, amount)

    except (ValueError, TypeError):
        await update.message.reply_text(_("wallet.charge.invalid_number"))
        return GET_CUSTOM_AMOUNT
    except Exception as e:
        LOGGER.error(f"Error handling custom amount: {e}")
        return GET_CUSTOM_AMOUNT



async def generate_charge_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from modules.financials.actions.payment import send_wallet_charge_invoice
    
    query = update.callback_query
    await query.answer(_("financials_payment.generating_invoice"))
    
    amount = context.user_data.get('charge_amount', 0)
    user_id = update.effective_user.id

    if amount <= 0:
        await query.edit_message_text(_("errors.internal_error"))
        return ConversationHandler.END

    plan_details = {
        "type": "wallet_charge",
        "amount": amount
    }

    invoice_id = await db_manager.create_pending_invoice(
        user_id=user_id,
        plan_details=plan_details,
        price=amount
    )

    if not invoice_id:
        await query.edit_message_text(_("financials_payment.error_creating_invoice_db"))
        return ConversationHandler.END

    # Delete the previous message (the confirmation panel)
    try:
        await query.message.delete()
    except Exception:
        pass
    
    # Send the real invoice
    await send_wallet_charge_invoice(context=context, user_id=user_id, invoice_id=invoice_id, amount=amount)

    # Clean up user_data
    context.user_data.pop('charge_amount', None)
    context.user_data.pop('wallet_panel_message', None)
    
    return ConversationHandler.END
async def back_to_wallet_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from .wallet import show_wallet_panel_as_edit
    query = update.callback_query
    await query.answer()
    await show_wallet_panel_as_edit(update, context)
    return DISPLAY_PANEL