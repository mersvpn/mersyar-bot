# FILE: modules/customer/actions/charge.py (FINAL CORRECTED AND REFACTORED VERSION)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from database import db_manager
from shared.translator import _
from .wallet import DISPLAY_PANEL

LOGGER = logging.getLogger(__name__)

# --- States ---
CHOOSE_AMOUNT, GET_CUSTOM_AMOUNT, CONFIRM_CHARGE = range(1, 4)

# --- Callback Data Constants ---
CALLBACK_PREFIX_AMOUNT = "wallet_charge_amount_"
CALLBACK_CUSTOM_AMOUNT = "wallet_charge_custom"
CALLBACK_CONFIRM_FINAL = "wallet_charge_confirm_final"
CALLBACK_CANCEL_CHARGE = "wallet_charge_cancel"


async def start_charge_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Starts the wallet charging process.
    (⭐ FIX ⭐) It now dynamically loads predefined amounts from the database.
    """
    query = update.callback_query
    await query.answer()

    # (✅) Dynamically load bot settings each time this is called.
    bot_settings = await db_manager.load_bot_settings()
    predefined_amounts = bot_settings.get("wallet_predefined_amounts")

    # If admin has disabled predefined amounts, go straight to custom amount entry.
    if not predefined_amounts:
        LOGGER.info("No predefined amounts set. Skipping to custom amount.")
        return await prompt_for_custom_amount(update, context)

    # Build the keyboard with the loaded amounts
    keyboard = []
    # Create rows with a maximum of 2 buttons per row
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
    """Shows the final confirmation message before generating an invoice."""
    query = update.callback_query
    
    context.user_data['charge_amount'] = amount
    
    text = _("wallet.charge.confirm_preview", amount=f"{amount:,}")
    
    keyboard = [
        [InlineKeyboardButton(_("wallet.charge.button_confirm_final"), callback_data=CALLBACK_CONFIRM_FINAL)],
        [InlineKeyboardButton(_("wallet.charge.button_cancel"), callback_data=CALLBACK_CANCEL_CHARGE)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        # If we came from a button click, edit the message directly.
        await query.answer()
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    elif 'wallet_panel_message_id' in context.user_data:
        # (⭐ FIX ⭐) If we came from a text message (custom amount),
        # use bot.edit_message_text with the saved chat_id and message_id.
        chat_id = update.effective_chat.id
        message_id = context.user_data['wallet_panel_message_id']
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        LOGGER.error("Could not find a message to edit for confirmation.")
        return ConversationHandler.END

    return CONFIRM_CHARGE


async def handle_predefined_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user selecting a predefined charge amount."""
    query = update.callback_query
    amount_str = query.data.replace(CALLBACK_PREFIX_AMOUNT, "")
    amount = int(amount_str)
    return await show_confirmation(update, context, amount)


async def prompt_for_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user to type in a custom charge amount."""
    query = update.callback_query
    await query.answer()
    
    # Save the message ID of the panel so we can edit it later.
    context.user_data['wallet_panel_message_id'] = query.message.message_id
    
    text = _("wallet.charge.prompt_for_custom_amount")
    
    keyboard = [[InlineKeyboardButton(_("wallet.charge.button_cancel"), callback_data=CALLBACK_CANCEL_CHARGE)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    return GET_CUSTOM_AMOUNT


async def handle_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the custom amount entered by the user."""
    amount_text = update.message.text
    try:
        amount = int(amount_text)
        min_amount = 10000 # You can move this to config.py later
        if amount < min_amount:
            await update.message.reply_text(_("wallet.charge.amount_too_low", min_amount=f"{min_amount:,}"))
            return GET_CUSTOM_AMOUNT
        
        # Clean up the user's message
        await update.message.delete()
        
        # Call confirmation with the original update object. No mock needed.
        return await show_confirmation(update, context, amount)

    except (ValueError, TypeError):
        await update.message.reply_text(_("wallet.charge.invalid_number"))
        return GET_CUSTOM_AMOUNT
    except Exception as e:
        LOGGER.error(f"Error handling custom amount: {e}")
        return GET_CUSTOM_AMOUNT


async def generate_charge_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Creates a database record for the invoice and sends it to the user."""
    from modules.payment.actions.wallet import send_wallet_charge_invoice
    
    query = update.callback_query
    await query.answer(_("financials_payment.generating_invoice"))
    
    amount = context.user_data.get('charge_amount', 0)
    user_id = update.effective_user.id

    if amount <= 0:
        await query.edit_message_text(_("errors.internal_error"))
        return ConversationHandler.END

    plan_details = {"invoice_type": "WALLET_CHARGE", "amount": amount}

    invoice_id = await db_manager.create_pending_invoice(
        user_id=user_id, plan_details=plan_details, price=amount
    )

    if not invoice_id:
        await query.edit_message_text(_("financials_payment.error_creating_invoice_db"))
        return ConversationHandler.END

    try:
        await query.message.delete()
    except Exception:
        pass
    
    await send_wallet_charge_invoice(context=context, user_id=user_id, invoice_id=invoice_id, amount=amount)

    context.user_data.clear()
    return ConversationHandler.END


async def back_to_wallet_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback for cancel buttons, returns to the main wallet panel."""
    from .wallet import show_wallet_panel_as_edit
    query = update.callback_query
    await query.answer()
    await show_wallet_panel_as_edit(update, context)
    return DISPLAY_PANEL