# FILE: modules/financials/actions/balance_management.py (REVISED AND STABILIZED)

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from database.db_manager import get_user_wallet_balance, increase_wallet_balance, decrease_wallet_balance, get_user_by_id
from shared.translator import _
from shared.keyboards import get_balance_management_keyboard, get_admin_main_menu_keyboard, get_financial_settings_keyboard
from .settings import show_financial_menu as show_financial_menu_inline # Renamed for clarity

LOGGER = logging.getLogger(__name__)

# States
GET_USER_ID, SHOW_USER_BALANCE, GET_AMOUNT = range(3)
# Actions
INCREASE, DECREASE = "increase", "decrease"

async def start_balance_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: Deletes the inline menu and shows the custom reply keyboard."""
    query = update.callback_query
    await query.answer()
    
    await query.message.delete()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=_("financials_balance.prompt_for_user_id"), 
        reply_markup=get_balance_management_keyboard()
    )
    return GET_USER_ID

async def process_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes user ID and shows the balance menu."""
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
    
    return await show_user_balance_menu(update, context, is_new_entry=True)

async def show_user_balance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, is_new_entry: bool = False) -> int:
    """Displays the menu for increasing/decreasing balance."""
    query = update.callback_query
    if query:
        await query.answer()
        
    user_id = context.user_data['managed_user_id']
    user_info = context.user_data['managed_user_info']
    balance = await get_user_wallet_balance(user_id) or 0.00
    
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
        [InlineKeyboardButton(_("financials_balance.button_back"), callback_data="balance_back_to_id_prompt")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if is_new_entry:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=reply_markup)
    else:
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    return SHOW_USER_BALANCE

async def prompt_for_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompts for amount or handles back button."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "balance_back_to_id_prompt":
        await query.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=_("financials_balance.prompt_for_user_id")
            # The reply keyboard is already shown, no need to send it again
        )
        return GET_USER_ID

    action = query.data.split('_')[1]
    context.user_data['balance_action'] = action
    
    prompt_text = _(f"financials_balance.prompt_for_{action}_amount")
    keyboard = [[InlineKeyboardButton(_("financials_balance.button_cancel_amount_entry"), callback_data="back_to_user_menu_from_amount")]]
    await query.edit_message_text(text=prompt_text, reply_markup=InlineKeyboardMarkup(keyboard))
    return GET_AMOUNT

async def process_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the amount, notifies the user, and returns to the user ID prompt."""
    try:
        amount = float(update.message.text.strip())
        if amount <= 0: raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(_("financials_balance.invalid_amount"))
        return GET_AMOUNT

    user_id = context.user_data['managed_user_id']
    action = context.user_data['balance_action']
    admin_name = update.effective_user.full_name
    
    # --- ✨ NEW: Notification Logic ✨ ---
    notification_text = ""
    new_balance = None
    success = False
    
    if action == INCREASE:
        new_balance = await increase_wallet_balance(user_id, amount)
        if new_balance is not None:
            notification_text = _("financials_balance.user_notification_increase", 
                                  amount=f"{int(amount):,}", 
                                  admin_name=admin_name, 
                                  new_balance=f"{int(new_balance):,}")
            success = True
    else: # DECREASE
        new_balance = await decrease_wallet_balance(user_id, amount)
        if new_balance is not None:
            notification_text = _("financials_balance.user_notification_decrease", 
                                  amount=f"{int(amount):,}", 
                                  admin_name=admin_name, 
                                  new_balance=f"{int(new_balance):,}")
            success = True

    if success:
        await update.message.reply_text(_("financials_balance.update_successful"))
        try:
            await context.bot.send_message(chat_id=user_id, text=notification_text)
        except Exception as e:
            LOGGER.warning(f"Could not send balance update notification to user {user_id}: {e}")
    else:
        # This will only be reached on a decrease failure
        await update.message.reply_text(_("financials_balance.decrease_failed_insufficient"))
            
    # Go back to asking for the next user ID, but without the extra keyboard
    await update.message.reply_text(_("financials_balance.prompt_for_user_id"))
    return GET_USER_ID

async def end_management_and_show_financial_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cleans up and exits the conversation, returning to the financial settings inline menu."""
    context.user_data.clear()
    
    # Send the main admin keyboard first
    await update.message.reply_text(
        text=_("financials_settings.back_to_financial_menu"), # Simple confirmation text
        reply_markup=get_admin_main_menu_keyboard()
    )
    
    # Use the imported inline menu function. It expects an Update object which we have.
    await show_financial_menu_inline(update, context)
    
    return ConversationHandler.END