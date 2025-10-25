# --- START OF FILE modules/customer/actions/charge.py ---
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.constants import ParseMode
from database.crud import bot_setting as crud_bot_setting
from database.crud import pending_invoice as crud_invoice
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

    bot_settings = await crud_bot_setting.load_bot_settings()
    predefined_amounts = bot_settings.get("wallet_predefined_amounts")

    if not predefined_amounts:
        LOGGER.info("No predefined amounts set. Skipping to custom amount.")
        return await prompt_for_custom_amount(update, context)

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
    
    context.user_data['charge_amount'] = amount
    
    text = _("wallet.charge.confirm_preview", amount=f"{amount:,}")
    
    keyboard = [
        [InlineKeyboardButton(_("wallet.charge.button_confirm_final"), callback_data=CALLBACK_CONFIRM_FINAL)],
        [InlineKeyboardButton(_("wallet.charge.button_cancel"), callback_data=CALLBACK_CANCEL_CHARGE)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if query:
        await query.answer()
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    elif 'wallet_panel_message_id' in context.user_data:
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
    query = update.callback_query
    amount_str = query.data.replace(CALLBACK_PREFIX_AMOUNT, "")
    amount = int(amount_str)
    return await show_confirmation(update, context, amount)


async def prompt_for_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    context.user_data['wallet_panel_message_id'] = query.message.message_id
    
    text = _("wallet.charge.prompt_for_custom_amount")
    
    keyboard = [[InlineKeyboardButton(_("wallet.charge.button_cancel"), callback_data=CALLBACK_CANCEL_CHARGE)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
    return GET_CUSTOM_AMOUNT


async def handle_custom_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    amount_text = update.message.text
    try:
        amount = int(amount_text)
        min_amount = 10000
        if amount < min_amount:
            await update.message.reply_text(_("wallet.charge.amount_too_low", min_amount=f"{min_amount:,}"))
            return GET_CUSTOM_AMOUNT
        
        await update.message.delete()
        
        return await show_confirmation(update, context, amount)

    except (ValueError, TypeError):
        await update.message.reply_text(_("wallet.charge.invalid_number"))
        return GET_CUSTOM_AMOUNT
    except Exception as e:
        LOGGER.error(f"Error handling custom amount: {e}")
        return GET_CUSTOM_AMOUNT


async def generate_charge_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from modules.payment.actions.wallet import send_wallet_charge_invoice
    
    query = update.callback_query
    await query.answer(_("financials_payment.generating_invoice"))
    
    amount = context.user_data.get('charge_amount', 0)
    user_id = update.effective_user.id

    if amount <= 0:
        await query.edit_message_text(_("errors.internal_error"))
        return ConversationHandler.END

    plan_details = {"invoice_type": "WALLET_CHARGE", "amount": amount}

    invoice_obj = await crud_invoice.create_pending_invoice({
        'user_id': user_id,
        'plan_details': plan_details,
        'price': amount
    })

    if not invoice_obj:
        await query.edit_message_text(_("financials_payment.error_creating_invoice_db"))
        return ConversationHandler.END

    try:
        await query.message.delete()
    except Exception:
        pass
    
    await send_wallet_charge_invoice(context=context, user_id=user_id, invoice_id=invoice_obj.invoice_id, amount=amount)

    context.user_data.clear()
    return ConversationHandler.END


async def back_to_wallet_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    from .wallet import show_wallet_panel_as_edit
    query = update.callback_query
    await query.answer()
    await show_wallet_panel_as_edit(update, context)
    return DISPLAY_PANEL

# --- END OF FILE modules/customer/actions/charge.py ---```