# FILE: modules/financials/actions/balance_management.py (FINAL - LOGIC ONLY)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler
from database.db_manager import get_user_wallet_balance, increase_wallet_balance, decrease_wallet_balance, get_user_by_id
from shared.translator import _
from .settings import show_financial_menu

LOGGER = logging.getLogger(__name__)

# --- States ---
GET_USER_ID, SHOW_USER_BALANCE, GET_AMOUNT = range(3)
# --- Actions ---
INCREASE, DECREASE = "increase", "decrease"


async def start_balance_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    text = _("financials_balance.prompt_for_user_id")
    # Add a cancel button to the very first step
    keyboard = [[InlineKeyboardButton(_("financials_balance.button_back"), callback_data="balance_back")]]
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard))
    return GET_USER_ID


async def process_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id = int(update.message.text.strip())
    except (ValueError, TypeError):
        await update.message.reply_text(_("financials_balance.user_not_found", user_id=update.message.text))
        return GET_USER_ID

    user_info = await get_user_by_id(user_id)
    if not user_info:
        await update.message.reply_text(_("financials_balance.user_not_found", user_id=user_id))
        return GET_USER_ID

    context.user_data['managed_user_id'] = user_id
    context.user_data['managed_user_info'] = user_info
    
    await update.message.delete()
    return await show_user_balance_menu(update, context)


async def show_user_balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = context.user_data['managed_user_id']
    user_info = context.user_data['managed_user_info']
    
    balance = await get_user_wallet_balance(user_id)
    balance = balance if balance is not None else 0.00
    
    text = _("financials_balance.user_info_title")
    text += _("financials_balance.user_info_details", 
              full_name=user_info.get('first_name', ''), 
              user_id=user_id, 
              balance=f"{int(balance):,}")
    text += _("financials_balance.menu_prompt")

    keyboard = [
        [
            InlineKeyboardButton(_("financials_balance.button_increase"), callback_data=f"balance_{INCREASE}"),
            InlineKeyboardButton(_("financials_balance.button_decrease"), callback_data=f"balance_{DECREASE}")
        ],
        [InlineKeyboardButton(_("financials_balance.button_back"), callback_data="balance_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)
        
    return SHOW_USER_BALANCE


async def prompt_for_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    action = query.data.split('_')[1]
    context.user_data['balance_action'] = action
    
    if action == INCREASE:
        prompt_text = _("financials_balance.prompt_for_increase_amount")
    else:
        prompt_text = _("financials_balance.prompt_for_decrease_amount")
        
    await query.answer()
    
    keyboard = [[InlineKeyboardButton(_("financials_balance.button_cancel_amount_entry"), callback_data="cancel_amount_entry")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text=prompt_text, reply_markup=reply_markup)
    return GET_AMOUNT


async def process_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.strip())
        if amount <= 0: raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(_("financials_balance.invalid_amount"))
        return GET_AMOUNT

    user_id = context.user_data['managed_user_id']
    action = context.user_data['balance_action']
    
    if action == INCREASE:
        await increase_wallet_balance(user_id, amount)
        await update.message.reply_text(_("financials_balance.update_successful"))
    else: # DECREASE
        new_balance = await decrease_wallet_balance(user_id, amount)
        if new_balance is not None:
            await update.message.reply_text(_("financials_balance.update_successful"))
        else:
            await update.message.reply_text(_("financials_balance.decrease_failed_insufficient"))
            
    # We need to manually delete the message where the user typed the amount
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id - 1)
        await update.message.delete()
    except Exception:
        pass # Ignore if messages can't be deleted

    return await show_user_balance_menu(update, context)


async def cancel_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    await query.edit_message_text(_("financials_balance.operation_cancelled"))
    # The END of conversation will be handled by the fallback which reroutes to the main financial menu
    return ConversationHandler.END